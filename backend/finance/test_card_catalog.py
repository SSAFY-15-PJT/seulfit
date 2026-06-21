from decimal import Decimal

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
