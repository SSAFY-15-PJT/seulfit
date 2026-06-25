from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from finance.card_gorilla_normalization import (
    parse_category_monthly_limit,
    parse_category_specific_limits,
    parse_minimum_transaction_amount,
    parse_channel_condition,
    parse_usage_limit,
)
from finance.models import CardProduct


class Command(BaseCommand):
    help = "선택한 카드고릴라 카드의 명확한 거래·한도 조건을 원문에서 다시 추출합니다."

    def add_arguments(self, parser):
        parser.add_argument("--card-id", action="append", type=int, required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        card_ids = sorted(set(options["card_id"]))
        cards = CardProduct.objects.filter(
            pk__in=card_ids,
            source_channel="card_gorilla",
        ).prefetch_related("benefits")
        found_ids = {card.pk for card in cards}
        missing_ids = sorted(set(card_ids) - found_ids)
        if missing_ids:
            raise CommandError(
                f"카드고릴라 카드가 아닌 ID 또는 존재하지 않는 ID: {missing_ids}"
            )

        changed = 0
        with transaction.atomic():
            for card in cards:
                for benefit in card.benefits.all():
                    updates = {}
                    minimum = parse_minimum_transaction_amount(benefit.raw_text)
                    category_limit = parse_category_monthly_limit(benefit.raw_text)
                    daily_usage = parse_usage_limit(benefit.raw_text, "일")
                    monthly_usage = parse_usage_limit(benefit.raw_text, "월")
                    scoped_limit, scoped_monthly_usage = (
                        parse_category_specific_limits(
                            benefit.category,
                            benefit.raw_text,
                        )
                    )
                    if category_limit is None:
                        category_limit = scoped_limit
                    if monthly_usage is None:
                        monthly_usage = scoped_monthly_usage
                    channel, _conditions = parse_channel_condition(
                        benefit.raw_text,
                        allow_explicit_channel=True,
                    )

                    if minimum and benefit.minimum_transaction_amount != minimum:
                        updates["minimum_transaction_amount"] = minimum
                    if (
                        category_limit is not None
                        and benefit.category_monthly_limit != category_limit
                    ):
                        updates["category_monthly_limit"] = category_limit
                    if daily_usage and benefit.daily_usage_limit != daily_usage:
                        updates["daily_usage_limit"] = daily_usage
                    if monthly_usage and benefit.monthly_usage_limit != monthly_usage:
                        updates["monthly_usage_limit"] = monthly_usage
                    if channel != "all" and benefit.channel != channel:
                        updates["channel"] = channel

                    if not updates:
                        continue
                    changed += 1
                    self.stdout.write(
                        f"card={card.pk} benefit={benefit.pk} updates={updates}"
                    )
                    if options["apply"]:
                        for field, value in updates.items():
                            setattr(benefit, field, value)
                        benefit.save(
                            update_fields=[*updates.keys(), "updated_at"]
                        )

            if not options["apply"]:
                transaction.set_rollback(True)

        self.stdout.write(
            f"cards={len(found_ids)} changed_benefits={changed} "
            f"apply={options['apply']}"
        )
