import json
from io import BytesIO

from django.test import TestCase, override_settings

from finance.graph_sync import (
    build_graph_sync_payload,
    build_graph_statements,
    sync_active_cards_to_neo4j,
)
from finance.models import (
    BenefitRule,
    CardProduct,
    CardType,
    DiscountType,
    ParseStatus,
)


class FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class GraphSyncTests(TestCase):
    def setUp(self):
        card = CardProduct.objects.create(
            external_id="active-card",
            issuer="카드사",
            provider="카드사",
            source_channel="test",
            card_type=CardType.CREDIT,
            name="활성 카드",
            source_url="https://example.com/card",
            annual_fee=10000,
            parse_status=ParseStatus.ACTIVE,
            raw_text="원문",
        )
        BenefitRule.objects.create(
            card=card,
            category="cafe",
            discount_type=DiscountType.RATE,
            discount_rate="0.1",
            raw_text="카페 10%",
            parse_status=ParseStatus.ACTIVE,
        )
        review_card = CardProduct.objects.create(
            external_id="review-card",
            issuer="카드사",
            provider="카드사",
            source_channel="test",
            card_type=CardType.CREDIT,
            name="검토 카드",
            source_url="https://example.com/review",
            annual_fee=10000,
            parse_status=ParseStatus.REVIEW_REQUIRED,
            raw_text="원문",
        )
        BenefitRule.objects.create(
            card=review_card,
            category="mart",
            discount_type=DiscountType.RATE,
            discount_rate="0.1",
            raw_text="마트 10%",
            parse_status=ParseStatus.ACTIVE,
        )

    def test_payload_contains_only_active_cards_and_benefits(self):
        payload = build_graph_sync_payload()

        self.assertEqual(len(payload.cards), 1)
        self.assertEqual(len(payload.benefits), 1)
        self.assertEqual(payload.cards[0]["name"], "활성 카드")
        self.assertEqual(payload.benefits[0]["category"], "cafe")
        self.assertEqual(len(build_graph_statements(payload)), 4)

    @override_settings(
        NEO4J_HTTP_URI="http://neo4j.test:7474",
        NEO4J_DATABASE="neo4j",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="secret",
    )
    def test_sync_posts_transaction_payload(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse(b'{"results":[],"errors":[]}')

        result = sync_active_cards_to_neo4j(opener=opener)

        self.assertEqual(
            captured["url"],
            "http://neo4j.test:7474/db/neo4j/tx/commit",
        )
        self.assertEqual(len(captured["body"]["statements"]), 4)
        self.assertEqual(captured["timeout"], 30)
        self.assertEqual(result["card_count"], 1)
