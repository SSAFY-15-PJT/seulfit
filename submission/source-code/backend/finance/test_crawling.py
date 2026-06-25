from email.message import Message
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from finance.crawling import (
    claim_next_item,
    download_image_atomic,
    enqueue_items,
    mark_item_failure,
    mark_item_success,
    recover_interrupted_job,
    run_crawl_job,
)
from finance.models import CrawlItem, CrawlJob, CrawlStatus


class FakeImageResponse(BytesIO):
    def __init__(self, content, content_type="image/png"):
        super().__init__(content)
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class CrawlingCheckpointTests(TestCase):
    def test_enqueue_items_is_idempotent_per_job_and_url(self):
        job = CrawlJob.objects.create(source_channel="shinhan")
        items = [{"external_id": "card-1", "source_url": "https://example.com/1"}]

        self.assertEqual(enqueue_items(job, items), 1)
        self.assertEqual(enqueue_items(job, items), 0)
        self.assertEqual(CrawlItem.objects.filter(job=job).count(), 1)

    def test_interrupted_fetching_item_returns_to_retry_pending(self):
        job = CrawlJob.objects.create(
            source_channel="kb",
            status=CrawlStatus.FETCHING,
        )
        item = CrawlItem.objects.create(
            job=job,
            source_url="https://example.com/1",
            status=CrawlStatus.FETCHING,
        )

        recover_interrupted_job(job)

        item.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(item.status, CrawlStatus.RETRY_PENDING)
        self.assertEqual(job.status, CrawlStatus.RETRY_PENDING)

    def test_successful_item_is_not_claimed_again(self):
        job = CrawlJob.objects.create(source_channel="samsung")
        enqueue_items(
            job,
            [
                {"source_url": "https://example.com/1"},
                {"source_url": "https://example.com/2"},
            ],
        )

        first = claim_next_item(job)
        mark_item_success(first, {"name": "첫 번째 카드"}, {"page": 1, "index": 1})
        second = claim_next_item(job)

        self.assertNotEqual(first.pk, second.pk)
        first.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(first.status, CrawlStatus.SUCCESS)
        self.assertEqual(job.success_count, 1)
        self.assertEqual(job.resume_cursor, {"page": 1, "index": 1})

    def test_connection_error_is_retried_then_failed(self):
        job = CrawlJob.objects.create(source_channel="hyundai")
        item = CrawlItem.objects.create(
            job=job,
            source_url="https://example.com/1",
            status=CrawlStatus.FETCHING,
        )

        for expected_retry_count in (1, 2, 3):
            mark_item_failure(item, URLError("offline"), max_retries=3)
            item.refresh_from_db()
            self.assertEqual(item.retry_count, expected_retry_count)
            self.assertEqual(item.status, CrawlStatus.RETRY_PENDING)
            item.status = CrawlStatus.FETCHING
            item.save(update_fields=["status", "updated_at"])

        mark_item_failure(item, URLError("offline"), max_retries=3)
        item.refresh_from_db()
        self.assertEqual(item.retry_count, 4)
        self.assertEqual(item.status, CrawlStatus.FAILED)

    def test_forbidden_response_pauses_only_its_job(self):
        paused_job = CrawlJob.objects.create(source_channel="kakaobank")
        other_job = CrawlJob.objects.create(
            source_channel="tossbank",
            status=CrawlStatus.FETCHING,
        )
        item = CrawlItem.objects.create(
            job=paused_job,
            source_url="https://example.com/1",
            status=CrawlStatus.FETCHING,
        )
        error = HTTPError(item.source_url, 403, "Forbidden", {}, None)

        failure = mark_item_failure(item, error)

        paused_job.refresh_from_db()
        other_job.refresh_from_db()
        self.assertTrue(failure.pause_channel)
        self.assertEqual(paused_job.status, CrawlStatus.PAUSED)
        self.assertEqual(other_job.status, CrawlStatus.FETCHING)

    def test_runner_retries_with_backoff_and_then_succeeds(self):
        job = CrawlJob.objects.create(source_channel="shinhan")
        enqueue_items(job, [{"source_url": "https://example.com/1"}])
        attempts = []
        delays = []

        def flaky_fetch(item):
            attempts.append(item.pk)
            if len(attempts) < 3:
                raise URLError("temporary offline")
            return {"name": "복구된 카드"}

        run_crawl_job(job, flaky_fetch, sleep_fn=delays.append)

        item = job.items.get()
        job.refresh_from_db()
        self.assertEqual(len(attempts), 3)
        self.assertEqual(delays, [2, 5])
        self.assertEqual(item.status, CrawlStatus.SUCCESS)
        self.assertEqual(job.status, CrawlStatus.SUCCESS)

    def test_runner_uses_all_backoff_delays_before_final_failure(self):
        job = CrawlJob.objects.create(source_channel="hyundai")
        enqueue_items(job, [{"source_url": "https://example.com/1"}])
        delays = []

        def offline_fetch(_item):
            raise URLError("offline")

        run_crawl_job(job, offline_fetch, sleep_fn=delays.append)

        item = job.items.get()
        self.assertEqual(delays, [2, 5, 15])
        self.assertEqual(item.retry_count, 4)
        self.assertEqual(item.status, CrawlStatus.FAILED)

    def test_process_interrupt_leaves_checkpoint_for_next_run(self):
        job = CrawlJob.objects.create(source_channel="kb")
        enqueue_items(job, [{"source_url": "https://example.com/1"}])

        def interrupted_fetch(_item):
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            run_crawl_job(job, interrupted_fetch, sleep_fn=lambda _delay: None)

        item = job.items.get()
        self.assertEqual(item.status, CrawlStatus.FETCHING)

        recover_interrupted_job(job)
        item.refresh_from_db()
        self.assertEqual(item.status, CrawlStatus.RETRY_PENDING)

    def test_resume_command_recovers_interrupted_item_without_reprocessing_success(self):
        job = CrawlJob.objects.create(
            source_channel="shinhan",
            status=CrawlStatus.FETCHING,
        )
        completed = CrawlItem.objects.create(
            job=job,
            source_url="https://example.com/completed",
            status=CrawlStatus.SUCCESS,
            raw_payload={"name": "완료 카드"},
        )
        interrupted = CrawlItem.objects.create(
            job=job,
            source_url="https://example.com/interrupted",
            status=CrawlStatus.FETCHING,
        )
        fetched_urls = []

        class ResumeAdapter:
            def run(self, job, retry_failed, limit, stdout):
                self.assert_resume_state(job)

                def fetch_item(item):
                    fetched_urls.append(item.source_url)
                    return {"name": "재개 카드"}

                return run_crawl_job(
                    job,
                    fetch_item,
                    retry_failed=retry_failed,
                    sleep_fn=lambda _delay: None,
                )

            @staticmethod
            def assert_resume_state(resumed_job):
                assert resumed_job.items.get(
                    source_url=interrupted.source_url
                ).status == CrawlStatus.RETRY_PENDING
                assert resumed_job.items.get(
                    source_url=completed.source_url
                ).status == CrawlStatus.SUCCESS

        source = SimpleNamespace(
            key="shinhan",
            label="신한카드",
            adapter=ResumeAdapter(),
            is_available=True,
        )
        with patch(
            "finance.management.commands.crawl_cards.get_source",
            return_value=source,
        ):
            call_command("crawl_cards", issuer="shinhan", resume=True)

        job.refresh_from_db()
        completed.refresh_from_db()
        interrupted.refresh_from_db()
        self.assertEqual(fetched_urls, [interrupted.source_url])
        self.assertEqual(completed.status, CrawlStatus.SUCCESS)
        self.assertEqual(interrupted.status, CrawlStatus.SUCCESS)
        self.assertEqual(job.success_count, 2)
        self.assertEqual(job.status, CrawlStatus.SUCCESS)

    def test_resume_retry_failed_retries_sustained_network_failure(self):
        job = CrawlJob.objects.create(
            source_channel="shinhan",
            status=CrawlStatus.FAILED,
        )
        failed = CrawlItem.objects.create(
            job=job,
            source_url="https://example.com/failed",
            status=CrawlStatus.FAILED,
            retry_count=4,
            last_error="offline",
        )
        retry_flags = []

        class RetryFailedAdapter:
            def run(self, job, retry_failed, limit, stdout):
                retry_flags.append(retry_failed)
                return run_crawl_job(
                    job,
                    lambda item: {"name": item.source_url},
                    retry_failed=retry_failed,
                    sleep_fn=lambda _delay: None,
                )

        source = SimpleNamespace(
            key="shinhan",
            label="신한카드",
            adapter=RetryFailedAdapter(),
            is_available=True,
        )
        with patch(
            "finance.management.commands.crawl_cards.get_source",
            return_value=source,
        ):
            call_command(
                "crawl_cards",
                issuer="shinhan",
                resume=True,
                retry_failed=True,
            )

        job.refresh_from_db()
        failed.refresh_from_db()
        self.assertEqual(retry_flags, [True])
        self.assertEqual(failed.status, CrawlStatus.SUCCESS)
        self.assertEqual(job.status, CrawlStatus.SUCCESS)

    def test_atomic_image_download_removes_partial_file_on_failure(self):
        def failing_opener(_request, timeout):
            raise URLError(f"offline after {timeout} seconds")

        with TemporaryDirectory() as directory:
            destination = f"{directory}/card.png"
            with self.assertRaises(URLError):
                download_image_atomic(
                    "https://example.com/card.png",
                    destination,
                    opener=failing_opener,
                )

            self.assertFalse(Path(destination).exists())
            self.assertFalse(Path(f"{destination}.part").exists())

    def test_atomic_image_download_moves_complete_image_to_final_path(self):
        def successful_opener(_request, timeout):
            self.assertEqual(timeout, 10)
            return FakeImageResponse(b"valid-image")

        with TemporaryDirectory() as directory:
            destination = f"{directory}/card.png"
            result = download_image_atomic(
                "https://example.com/card.png",
                destination,
                opener=successful_opener,
            )

            self.assertEqual(Path(destination).read_bytes(), b"valid-image")
            self.assertEqual(result["content_type"], "image/png")
            self.assertFalse(Path(f"{destination}.part").exists())
