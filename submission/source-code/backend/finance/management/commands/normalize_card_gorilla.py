import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from finance.card_gorilla_normalization import (
    normalize_name,
    parse_card_gorilla_payload,
)
from finance.card_ingestion import persist_parsed_card
from finance.models import CardProduct, CrawlJob, CrawlStatus


class Command(BaseCommand):
    help = "카드고릴라 원문 수집 결과를 검수 대기 카드로 정규화합니다."

    def add_arguments(self, parser):
        parser.add_argument("--job-id", type=int)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        queryset = CrawlJob.objects.filter(
            source_channel="card_gorilla",
            status=CrawlStatus.SUCCESS,
        )
        if options["job_id"]:
            queryset = queryset.filter(pk=options["job_id"])
        job = queryset.order_by("-created_at").first()
        if not job:
            raise CommandError("정규화할 카드고릴라 수집 작업이 없습니다.")

        existing = {
            (
                normalize_name(card.issuer),
                normalize_name(card.name),
                card.card_type,
            ): card
            for card in CardProduct.objects.exclude(source_channel="card_gorilla")
        }
        created = 0
        updated = 0
        duplicates = 0
        skipped = 0

        with transaction.atomic():
            for item in job.items.filter(status=CrawlStatus.SUCCESS):
                parsed = parse_card_gorilla_payload(item.raw_payload)
                duplicate = existing.get(
                    (
                        normalize_name(parsed["issuer"]),
                        normalize_name(parsed["name"]),
                        parsed["card_type"],
                    )
                )
                if duplicate:
                    duplicates += 1
                    item.raw_payload["normalization"] = {
                        "status": "duplicate",
                        "existing_card_id": duplicate.pk,
                    }
                    item.save(update_fields=["raw_payload", "updated_at"])
                    continue
                if not parsed["external_id"] or not parsed["name"]:
                    skipped += 1
                    continue

                was_existing = CardProduct.objects.filter(
                    source_channel="card_gorilla",
                    external_id=parsed["external_id"],
                ).exists()
                card, _validation = persist_parsed_card(
                    item,
                    parsed,
                    json.dumps(item.raw_payload, ensure_ascii=False),
                )
                item.raw_payload["normalization"] = {
                    "status": "review_required",
                    "card_id": card.pk,
                }
                item.save(update_fields=["raw_payload", "updated_at"])
                if was_existing:
                    updated += 1
                else:
                    created += 1

            if options["dry_run"]:
                transaction.set_rollback(True)

        self.stdout.write(
            f"job={job.pk} created={created} updated={updated} "
            f"duplicates={duplicates} skipped={skipped} "
            f"dry_run={options['dry_run']}"
        )
