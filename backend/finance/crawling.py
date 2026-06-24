import socket
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import CrawlItem, CrawlJob, CrawlStatus


TRANSIENT_HTTP_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
PAUSE_HTTP_STATUS_CODES = {403, 429}
RETRY_DELAYS_SECONDS = (2, 5, 15)


@dataclass(frozen=True)
class CrawlFailure:
    retryable: bool
    pause_channel: bool
    message: str


def classify_crawl_error(error):
    if isinstance(error, HTTPError):
        return CrawlFailure(
            retryable=error.code in TRANSIENT_HTTP_STATUS_CODES,
            pause_channel=error.code in PAUSE_HTTP_STATUS_CODES,
            message=f"HTTP {error.code}: {error.reason}",
        )
    if isinstance(error, (URLError, TimeoutError, ConnectionError, socket.timeout)):
        return CrawlFailure(retryable=True, pause_channel=False, message=str(error))
    return CrawlFailure(retryable=False, pause_channel=False, message=str(error))


@transaction.atomic
def recover_interrupted_job(job):
    CrawlItem.objects.filter(job=job, status=CrawlStatus.FETCHING).update(
        status=CrawlStatus.RETRY_PENDING,
        last_error="이전 실행이 완료되기 전에 중단됨",
    )
    job.status = CrawlStatus.RETRY_PENDING
    job.last_checkpoint_at = timezone.now()
    job.save(update_fields=["status", "last_checkpoint_at", "updated_at"])
    refresh_job_counts(job)
    return job


@transaction.atomic
def enqueue_items(job, items):
    created_count = 0
    for item in items:
        _, created = CrawlItem.objects.get_or_create(
            job=job,
            source_url=item["source_url"],
            defaults={"external_id": item.get("external_id", "")},
        )
        created_count += int(created)

    job.total_count = job.items.count()
    job.last_checkpoint_at = timezone.now()
    job.save(update_fields=["total_count", "last_checkpoint_at", "updated_at"])
    return created_count


@transaction.atomic
def claim_next_item(job, retry_failed=False):
    statuses = [CrawlStatus.PENDING, CrawlStatus.RETRY_PENDING]
    if retry_failed:
        statuses.append(CrawlStatus.FAILED)

    item = (
        CrawlItem.objects.select_for_update()
        .filter(job=job, status__in=statuses)
        .order_by("pk")
        .first()
    )
    if item is None:
        return None

    item.status = CrawlStatus.FETCHING
    item.last_attempted_at = timezone.now()
    item.last_error = ""
    item.save(
        update_fields=[
            "status",
            "last_attempted_at",
            "last_error",
            "updated_at",
        ]
    )
    job.status = CrawlStatus.FETCHING
    job.started_at = job.started_at or timezone.now()
    job.last_checkpoint_at = timezone.now()
    job.save(
        update_fields=[
            "status",
            "started_at",
            "last_checkpoint_at",
            "updated_at",
        ]
    )
    return item


@transaction.atomic
def mark_item_success(item, raw_payload, resume_cursor=None):
    now = timezone.now()
    item.status = CrawlStatus.SUCCESS
    item.raw_payload = raw_payload or {}
    item.last_error = ""
    item.completed_at = now
    item.save(
        update_fields=[
            "status",
            "raw_payload",
            "last_error",
            "completed_at",
            "updated_at",
        ]
    )

    job = item.job
    if resume_cursor is not None:
        job.resume_cursor = resume_cursor
    job.last_checkpoint_at = now
    job.save(update_fields=["resume_cursor", "last_checkpoint_at", "updated_at"])
    refresh_job_counts(job)


@transaction.atomic
def mark_item_failure(item, error, max_retries=3):
    failure = classify_crawl_error(error)
    item.retry_count += 1
    item.last_error = failure.message

    if failure.pause_channel:
        item.status = CrawlStatus.RETRY_PENDING
        item.job.status = CrawlStatus.PAUSED
    elif failure.retryable and item.retry_count <= max_retries:
        item.status = CrawlStatus.RETRY_PENDING
        item.job.status = CrawlStatus.RETRY_PENDING
    else:
        item.status = CrawlStatus.FAILED
        item.job.status = CrawlStatus.FAILED
        item.completed_at = timezone.now()

    item.save(
        update_fields=[
            "status",
            "retry_count",
            "last_error",
            "completed_at",
            "updated_at",
        ]
    )
    item.job.last_error = failure.message
    item.job.last_checkpoint_at = timezone.now()
    item.job.save(
        update_fields=[
            "status",
            "last_error",
            "last_checkpoint_at",
            "updated_at",
        ]
    )
    refresh_job_counts(item.job)
    return failure


def refresh_job_counts(job):
    counts = job.items.aggregate(
        total=Count("id"),
        success=Count("id", filter=Q(status=CrawlStatus.SUCCESS)),
        failed=Count("id", filter=Q(status=CrawlStatus.FAILED)),
    )
    CrawlJob.objects.filter(pk=job.pk).update(
        total_count=counts["total"],
        success_count=counts["success"],
        failed_count=counts["failed"],
    )
    job.refresh_from_db(
        fields=["total_count", "success_count", "failed_count", "status"]
    )


@transaction.atomic
def complete_job_if_finished(job):
    has_remaining = job.items.exclude(
        status__in=[CrawlStatus.SUCCESS, CrawlStatus.FAILED]
    ).exists()
    if has_remaining:
        return False

    job.status = CrawlStatus.SUCCESS if job.failed_count == 0 else CrawlStatus.FAILED
    job.completed_at = timezone.now()
    job.last_checkpoint_at = job.completed_at
    job.save(
        update_fields=[
            "status",
            "completed_at",
            "last_checkpoint_at",
            "updated_at",
        ]
    )
    return True


def run_crawl_job(
    job,
    fetch_item,
    retry_failed=False,
    max_retries=3,
    sleep_fn=time.sleep,
):
    while True:
        item = claim_next_item(job, retry_failed=retry_failed)
        if item is None:
            complete_job_if_finished(job)
            return job

        try:
            result = fetch_item(item)
            if isinstance(result, tuple):
                raw_payload, resume_cursor = result
            else:
                raw_payload, resume_cursor = result, None
            mark_item_success(item, raw_payload, resume_cursor=resume_cursor)
        except Exception as error:
            failure = mark_item_failure(item, error, max_retries=max_retries)
            if failure.pause_channel:
                return job
            if failure.retryable and item.retry_count <= max_retries:
                delay_index = min(item.retry_count - 1, len(RETRY_DELAYS_SECONDS) - 1)
                sleep_fn(RETRY_DELAYS_SECONDS[delay_index])

        job.refresh_from_db()


def download_image_atomic(
    source_url,
    destination,
    timeout=10,
    max_bytes=10 * 1024 * 1024,
    opener=urlopen,
):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.with_suffix(f"{destination.suffix}.part")
    request = Request(source_url, headers={"User-Agent": "SeulPickCardCrawler/1.0"})

    try:
        with opener(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type()
            if not content_type.startswith("image/"):
                raise ValueError(f"지원하지 않는 이미지 콘텐츠 타입: {content_type}")

            content = response.read(max_bytes + 1)
            if len(content) > max_bytes:
                raise ValueError("이미지 크기가 제한을 초과함")
            if not content:
                raise ValueError("빈 이미지 응답")

            temporary_path.write_bytes(content)
            temporary_path.replace(destination)
            return {
                "path": str(destination),
                "content_type": content_type,
                "size": len(content),
                "checksum": sha256(content).hexdigest(),
            }
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
