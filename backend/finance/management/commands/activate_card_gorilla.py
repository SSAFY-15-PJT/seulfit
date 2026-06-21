from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from finance.card_gorilla_activation import (
    apply_card_gorilla_activation,
    evaluate_card_gorilla_activation,
)
from finance.models import CardProduct


class Command(BaseCommand):
    help = "완전히 구조화된 카드고릴라 혜택만 추천용으로 활성화합니다."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        decisions = []
        blocker_counts = Counter()
        activated = 0

        with transaction.atomic():
            for card in CardProduct.objects.filter(
                source_channel="card_gorilla",
            ).prefetch_related("benefits"):
                decision = evaluate_card_gorilla_activation(card)
                decisions.append(decision)
                blocker_counts.update(decision.card_blockers)
                for blockers in decision.blocked_benefits.values():
                    blocker_counts.update(blockers)
                if options["apply"] and apply_card_gorilla_activation(
                    card,
                    decision,
                ):
                    activated += 1

        ready = sum(decision.can_activate for decision in decisions)
        self.stdout.write(
            f"cards={len(decisions)} ready={ready} activated={activated} "
            f"apply={options['apply']}"
        )
        for reason, count in sorted(blocker_counts.items()):
            self.stdout.write(f"{reason}\t{count}")
