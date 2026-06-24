from django.test import TestCase

from finance.card_activation import (
    activate_card_if_ready,
    evaluate_card_activation,
)
from finance.models import (
    BenefitRule,
    CardProduct,
    CardType,
    DiscountType,
    ParseStatus,
)


class CardActivationTests(TestCase):
    def create_card(self, annual_fee=10000):
        return CardProduct.objects.create(
            external_id="activation-card",
            issuer="카드사",
            provider="카드사",
            source_channel="test",
            card_type=CardType.CREDIT,
            name="활성화 카드",
            source_url="https://example.com/card",
            annual_fee=annual_fee,
            previous_month_requirement=0,
            parse_status=ParseStatus.REVIEW_REQUIRED,
            raw_text="원문",
        )

    def test_missing_fee_and_review_benefit_block_activation(self):
        card = self.create_card(annual_fee=None)
        BenefitRule.objects.create(
            card=card,
            category="cafe",
            discount_type=DiscountType.RATE,
            discount_rate="0.1",
            raw_text="카페 10%",
            parse_status=ParseStatus.REVIEW_REQUIRED,
        )

        result = evaluate_card_activation(card)

        self.assertFalse(result.is_ready)
        self.assertIn("annual_fee_missing", result.blockers)
        self.assertIn("no_active_benefits", result.blockers)
        self.assertIn("partial_benefit_coverage", result.warnings)

    def test_ready_card_is_activated(self):
        card = self.create_card()
        BenefitRule.objects.create(
            card=card,
            category="cafe",
            discount_type=DiscountType.RATE,
            discount_rate="0.1",
            raw_text="카페 10%",
            parse_status=ParseStatus.ACTIVE,
        )

        result = activate_card_if_ready(card)

        card.refresh_from_db()
        self.assertTrue(result.is_ready)
        self.assertEqual(card.parse_status, ParseStatus.ACTIVE)

    def test_review_benefit_is_warning_when_active_benefit_exists(self):
        card = self.create_card()
        BenefitRule.objects.create(
            card=card,
            category="cafe",
            discount_type=DiscountType.RATE,
            discount_rate="0.05",
            raw_text="스타벅스 5%",
            parse_status=ParseStatus.ACTIVE,
        )
        BenefitRule.objects.create(
            card=card,
            category="etc",
            discount_type=DiscountType.RATE,
            discount_rate="0.1",
            raw_text="미지원 혜택",
            parse_status=ParseStatus.REVIEW_REQUIRED,
        )

        result = activate_card_if_ready(card)

        card.refresh_from_db()
        self.assertTrue(result.is_ready)
        self.assertIn("partial_benefit_coverage", result.warnings)
        self.assertEqual(card.parse_status, ParseStatus.ACTIVE)
        self.assertTrue(card.review_reasons)
