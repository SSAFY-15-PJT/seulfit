from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from finance.card_catalog import (
    card_product_to_recommendation_input,
    load_recommendation_candidates,
)
from finance.models import (
    BenefitRule,
    CardBenefitTier,
    CardProduct,
    CardType,
    DiscountType,
    ParseStatus,
)


def create_card(parse_status=ParseStatus.ACTIVE, annual_fee=12000):
    return CardProduct.objects.create(
        external_id=f"card-{parse_status}",
        issuer="테스트카드",
        provider="테스트카드",
        source_channel="test",
        card_type=CardType.CREDIT,
        name=f"{parse_status} 카드",
        source_url=f"https://example.com/{parse_status}",
        annual_fee=annual_fee,
        previous_month_requirement=300000,
        monthly_discount_limit=None,
        parse_status=parse_status,
        raw_text="카드 원문",
    )


class CardCatalogTests(TestCase):
    def test_active_card_is_converted_to_recommendation_input(self):
        card = create_card()
        BenefitRule.objects.create(
            card=card,
            category="cafe",
            discount_type=DiscountType.RATE,
            discount_rate=Decimal("0.1"),
            raw_text="카페 10% 할인",
            parse_status=ParseStatus.ACTIVE,
        )
        CardBenefitTier.objects.create(
            card=card,
            scope="card_total",
            minimum_spending=300000,
            maximum_spending=None,
            monthly_discount_limit=20000,
            raw_text="30만원 이상 2만원",
        )

        data = card_product_to_recommendation_input(card)

        self.assertEqual(data["id"], card.pk)
        self.assertEqual(data["focus"], ["cafe"])
        self.assertEqual(data["benefits"][0]["discount_rate"], 0.1)
        self.assertIsNone(data["annual_fee_verified_at"])
        self.assertEqual(
            data["benefit_tiers"][0]["monthly_discount_limit"],
            20000,
        )

    def test_display_only_conditions_are_exposed_for_frontend(self):
        card = create_card()
        BenefitRule.objects.create(
            card=card,
            category="shopping",
            discount_type=DiscountType.RATE,
            discount_rate=Decimal("0.1"),
            raw_text="간편결제 10% 할인, KB Pay로 결제 시 제공",
            parse_status=ParseStatus.ACTIVE,
            unsupported_conditions=["payment_method_condition"],
        )

        data = card_product_to_recommendation_input(card)

        self.assertEqual(
            data["benefits"][0]["display_only_conditions"],
            ["payment_method_condition"],
        )
        self.assertEqual(
            data["benefits"][0]["calculation_blockers"],
            [],
        )

    def test_review_required_card_is_excluded_and_counted(self):
        create_card(parse_status=ParseStatus.REVIEW_REQUIRED, annual_fee=None)

        catalog = load_recommendation_candidates()

        self.assertEqual(catalog["cards"], [])
        self.assertEqual(catalog["metadata"]["candidate_count"], 0)
        self.assertEqual(catalog["metadata"]["excluded_review_count"], 1)
        self.assertEqual(
            catalog["metadata"]["fallback_reason"],
            "no_active_cards",
        )

    def test_active_card_without_fee_or_active_benefit_is_unready(self):
        create_card(parse_status=ParseStatus.ACTIVE, annual_fee=None)

        catalog = load_recommendation_candidates()

        self.assertEqual(catalog["cards"], [])
        self.assertEqual(catalog["metadata"]["excluded_unready_count"], 1)

    @patch("finance.graph_repository.GraphRepository.find_card_candidates_by_area")
    def test_area_id_uses_neo4j_candidates_to_filter_sqlite_cards(
        self,
        find_candidates,
    ):
        matched = create_card()
        other = CardProduct.objects.create(
            external_id="other-card",
            issuer="테스트카드",
            provider="테스트카드",
            source_channel="test",
            card_type=CardType.CREDIT,
            name="다른 카드",
            source_url="https://example.com/other-card",
            annual_fee=12000,
            previous_month_requirement=300000,
            parse_status=ParseStatus.ACTIVE,
            raw_text="카드 원문",
        )
        for card in (matched, other):
            BenefitRule.objects.create(
                card=card,
                category="cafe",
                discount_type=DiscountType.RATE,
                discount_rate=Decimal("0.1"),
                raw_text="카페 10% 할인",
                parse_status=ParseStatus.ACTIVE,
            )
        find_candidates.return_value = [
            {
                "card_key": f"seulpick:{matched.source_channel}:{matched.external_id}",
                "category_key": "cafe",
                "store_count": 5,
                "area_store_count": 25,
                "category_share": 0.2,
            }
        ]

        catalog = load_recommendation_candidates(area_id="gangnam_station")

        self.assertEqual(catalog["metadata"]["recommendation_source"], "neo4j")
        self.assertEqual(catalog["metadata"]["graph_status"], "matched")
        self.assertEqual(catalog["metadata"]["graph_candidate_count"], 1)
        self.assertEqual(catalog["metadata"]["candidate_count"], 1)
        self.assertEqual(catalog["cards"][0]["id"], matched.pk)
        self.assertEqual(catalog["cards"][0]["graph_rerank_score"], 52.0)
        self.assertEqual(catalog["cards"][0]["graph_top_category"], "cafe")
        self.assertEqual(
            catalog["cards"][0]["graph_matched_categories"],
            ["cafe"],
        )

    @patch("finance.graph_repository.GraphRepository.find_card_candidates_by_area")
    def test_area_id_falls_back_to_sqlite_when_graph_has_no_candidates(
        self,
        find_candidates,
    ):
        card = create_card()
        BenefitRule.objects.create(
            card=card,
            category="cafe",
            discount_type=DiscountType.RATE,
            discount_rate=Decimal("0.1"),
            raw_text="카페 10% 할인",
            parse_status=ParseStatus.ACTIVE,
        )
        find_candidates.return_value = []

        catalog = load_recommendation_candidates(area_id="empty_area")

        self.assertEqual(catalog["metadata"]["recommendation_source"], "sqlite")
        self.assertEqual(catalog["metadata"]["graph_status"], "no_candidates")
        self.assertEqual(catalog["metadata"]["graph_candidate_count"], 0)
        self.assertEqual(
            catalog["metadata"]["graph_fallback_reason"],
            "no_graph_candidates",
        )
        self.assertEqual(catalog["metadata"]["candidate_count"], 1)
        self.assertEqual(catalog["cards"][0]["id"], card.pk)

    @patch("finance.graph_repository.GraphRepository.find_card_candidates_by_area")
    def test_area_id_falls_back_to_sqlite_when_graph_is_unavailable(
        self,
        find_candidates,
    ):
        card = create_card()
        BenefitRule.objects.create(
            card=card,
            category="cafe",
            discount_type=DiscountType.RATE,
            discount_rate=Decimal("0.1"),
            raw_text="카페 10% 할인",
            parse_status=ParseStatus.ACTIVE,
        )
        find_candidates.side_effect = RuntimeError("connection refused")

        catalog = load_recommendation_candidates(area_id="broken_area")

        self.assertEqual(catalog["metadata"]["recommendation_source"], "sqlite")
        self.assertEqual(catalog["metadata"]["graph_status"], "unavailable")
        self.assertIsNone(catalog["metadata"]["graph_candidate_count"])
        self.assertEqual(
            catalog["metadata"]["graph_fallback_reason"],
            "neo4j_unavailable",
        )
        self.assertEqual(catalog["metadata"]["candidate_count"], 1)
        self.assertEqual(catalog["cards"][0]["id"], card.pk)
