from django.utils import timezone

from django.core.management.base import BaseCommand, CommandError

from finance.card_activation import (
    activate_card_if_ready,
    evaluate_card_activation,
    revalidate_card_benefits,
)
from finance.models import CardProduct


class Command(BaseCommand):
    help = "카드의 추천 활성화 조건을 검사하고 준비된 카드만 active로 전환합니다."

    def add_arguments(self, parser):
        parser.add_argument("--card-id", type=int)
        parser.add_argument("--activate", action="store_true")
        parser.add_argument("--revalidate-benefits", action="store_true")
        parser.add_argument("--annual-fee", type=int)
        parser.add_argument("--annual-fee-source-url")

    def handle(self, *args, **options):
        queryset = CardProduct.objects.prefetch_related("benefits")
        if options["card_id"]:
            queryset = queryset.filter(pk=options["card_id"])
        if not queryset.exists():
            raise CommandError("검사할 카드가 없습니다.")
        if options["annual_fee"] is not None and not options["card_id"]:
            raise CommandError("연회비 입력에는 --card-id가 필요합니다.")
        if options["annual_fee"] is not None and not options["annual_fee_source_url"]:
            raise CommandError("연회비 입력에는 --annual-fee-source-url이 필요합니다.")

        for card in queryset:
            if options["annual_fee"] is not None:
                card.annual_fee = options["annual_fee"]
                card.annual_fee_source_url = options["annual_fee_source_url"]
                card.annual_fee_verified_at = timezone.now()
                card.review_reasons = [
                    reason
                    for reason in card.review_reasons
                    if "연회비" not in reason
                ]
                card.save(
                    update_fields=[
                        "annual_fee",
                        "annual_fee_source_url",
                        "annual_fee_verified_at",
                        "review_reasons",
                        "updated_at",
                    ]
                )
            if options["revalidate_benefits"]:
                revalidate_card_benefits(card)
            result = (
                activate_card_if_ready(card)
                if options["activate"]
                else evaluate_card_activation(card)
            )
            status = "ready" if result.is_ready else "blocked"
            blockers = ", ".join(result.blockers) or "-"
            warnings = ", ".join(result.warnings) or "-"
            self.stdout.write(
                f"{card.pk}\t{card.name}\t{status}\t{blockers}\t{warnings}"
            )
