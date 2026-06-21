from django.core.management.base import BaseCommand

from finance.graph_sync import (
    build_graph_sync_payload,
    build_graph_statements,
    sync_active_cards_to_neo4j,
)


class Command(BaseCommand):
    help = "SQLite의 active 카드와 혜택을 Neo4j에 동기화합니다."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        if options["dry_run"]:
            payload = build_graph_sync_payload()
            statements = build_graph_statements(payload)
            self.stdout.write(
                f"dry-run\tcards={len(payload.cards)}\t"
                f"benefits={len(payload.benefits)}\t"
                f"statements={len(statements)}"
            )
            return

        result = sync_active_cards_to_neo4j()
        self.stdout.write(
            self.style.SUCCESS(
                f"synced\tcards={result['card_count']}\t"
                f"benefits={result['benefit_count']}\t"
                f"endpoint={result['endpoint']}"
            )
        )
