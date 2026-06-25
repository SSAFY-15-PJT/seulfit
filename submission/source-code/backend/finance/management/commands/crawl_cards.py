from django.core.management.base import BaseCommand, CommandError

from finance.adapters.base import CollectionPolicyBlocked
from finance.crawler_registry import SOURCES, get_source
from finance.crawling import recover_interrupted_job
from finance.models import CrawlJob, CrawlStatus


class Command(BaseCommand):
    help = "카드사별 크롤링 작업을 생성하거나 중단된 작업을 재개합니다."

    def add_arguments(self, parser):
        parser.add_argument("--issuer", dest="source_channel", choices=sorted(SOURCES))
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--retry-failed", action="store_true")
        parser.add_argument("--list-sources", action="store_true")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        if options["list_sources"]:
            for source in SOURCES.values():
                availability = "available" if source.is_available else "planned"
                self.stdout.write(f"{source.key}\t{source.label}\t{availability}")
            return

        source_channel = options["source_channel"]
        if not source_channel:
            raise CommandError("--issuer 또는 --list-sources를 지정해야 합니다.")

        source = get_source(source_channel)
        if options["resume"]:
            job = (
                CrawlJob.objects.filter(
                    source_channel=source_channel,
                    status__in=[
                        CrawlStatus.FETCHING,
                        CrawlStatus.RETRY_PENDING,
                        CrawlStatus.PAUSED,
                        CrawlStatus.FAILED,
                    ],
                )
                .order_by("-created_at")
                .first()
            )
            if job is None:
                raise CommandError("재개할 크롤링 작업이 없습니다.")
            recover_interrupted_job(job)
        else:
            job = CrawlJob.objects.create(source_channel=source_channel)

        if not source.is_available:
            self.stdout.write(
                self.style.WARNING(
                    f"{source.label} 작업 #{job.pk}의 체크포인트를 준비했습니다. "
                    "사이트별 어댑터는 아직 구현되지 않았습니다."
                )
            )
            return

        try:
            source.adapter.run(
                job=job,
                retry_failed=options["retry_failed"],
                limit=options["limit"],
                stdout=self.stdout,
            )
        except CollectionPolicyBlocked as error:
            job.status = CrawlStatus.PAUSED
            job.last_error = str(error)
            job.save(update_fields=["status", "last_error", "updated_at"])
            self.stdout.write(self.style.WARNING(str(error)))
