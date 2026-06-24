from decimal import Decimal

from django.test import TestCase

from finance.card_gorilla_activation import (
    apply_card_gorilla_activation,
    collect_display_only_conditions,
    evaluate_benefit_for_activation,
    evaluate_card_gorilla_activation,
)
from finance.models import (
    BenefitRule,
    CardProduct,
    CardType,
    DiscountType,
    ParseStatus,
)


class CardGorillaActivationTests(TestCase):
    def create_card(self, annual_fee=0):
        return CardProduct.objects.create(
            external_id="gorilla-card",
            issuer="테스트카드",
            provider="카드고릴라",
            source_channel="card_gorilla",
            card_type=CardType.DEBIT,
            name="테스트 체크카드",
            source_url="https://www.card-gorilla.com/card/detail/1",
            annual_fee=annual_fee,
            previous_month_requirement=0,
            parse_status=ParseStatus.REVIEW_REQUIRED,
            raw_text="원문",
        )

    def test_generic_category_without_complex_condition_can_activate(self):
        card = self.create_card()
        benefit = BenefitRule.objects.create(
            card=card,
            category="convenience",
            discount_type=DiscountType.RATE,
            discount_rate="0.01",
            raw_text="편의점 업종 1% 적립, 한도 제한 없음",
            parse_status=ParseStatus.REVIEW_REQUIRED,
            unsupported_conditions=["source_review_required"],
        )

        decision = evaluate_card_gorilla_activation(card)
        self.assertTrue(decision.can_activate)

        self.assertTrue(apply_card_gorilla_activation(card, decision))
        card.refresh_from_db()
        benefit.refresh_from_db()
        self.assertEqual(card.parse_status, ParseStatus.ACTIVE)
        self.assertEqual(benefit.parse_status, ParseStatus.ACTIVE)

    def test_shared_limit_and_merchant_scope_stay_in_review(self):
        card = self.create_card()
        BenefitRule.objects.create(
            card=card,
            category="delivery",
            discount_type=DiscountType.RATE,
            discount_rate="0.1",
            raw_text="배달의민족 10% 할인, 월 통합 할인한도 5천원",
            parse_status=ParseStatus.REVIEW_REQUIRED,
        )

        decision = evaluate_card_gorilla_activation(card)

        self.assertFalse(decision.can_activate)
        blockers = next(iter(decision.blocked_benefits.values()))
        self.assertIn("shared_limit", blockers)
        self.assertIn("merchant_scope_required", blockers)

    def test_shared_limit_does_not_block_when_card_limit_is_parsed(self):
        card = self.create_card()
        card.monthly_discount_limit = 50000
        card.save(update_fields=["monthly_discount_limit", "updated_at"])
        BenefitRule.objects.create(
            card=card,
            category="convenience",
            discount_type=DiscountType.RATE,
            discount_rate="0.05",
            merchant_scope=["GS25", "CU"],
            raw_text="GS25, CU 5% 할인, 본인회원 기준으로 월간 통합할인한도 내에서 혜택이 제공됩니다.",
            parse_status=ParseStatus.REVIEW_REQUIRED,
        )

        decision = evaluate_card_gorilla_activation(card)

        self.assertTrue(decision.can_activate)
        self.assertEqual(decision.blocked_benefits, {})

    def test_missing_annual_fee_blocks_otherwise_safe_card(self):
        card = self.create_card(annual_fee=None)
        BenefitRule.objects.create(
            card=card,
            category="dining",
            discount_type=DiscountType.RATE,
            discount_rate="0.01",
            raw_text="음식점 업종 1% 적립, 한도 제한 없음",
            parse_status=ParseStatus.REVIEW_REQUIRED,
        )

        decision = evaluate_card_gorilla_activation(card)

        self.assertFalse(decision.can_activate)
        self.assertIn("annual_fee_missing", decision.card_blockers)

    def test_parsed_minimum_and_monthly_limit_do_not_block_activation(self):
        card = self.create_card()
        BenefitRule.objects.create(
            card=card,
            category="dining",
            discount_type=DiscountType.RATE,
            discount_rate="0.1",
            minimum_transaction_amount=10000,
            monthly_usage_limit=5,
            category_monthly_limit=5000,
            raw_text=(
                "음식점 업종 10% 할인, 건당 1만원 이상, "
                "월 5회, 월 할인한도 5천원"
            ),
            parse_status=ParseStatus.REVIEW_REQUIRED,
        )

        decision = evaluate_card_gorilla_activation(card)

        self.assertTrue(decision.can_activate)

    def test_delivery_with_merchant_scope_passes_scope_check(self):
        card = self.create_card()
        BenefitRule.objects.create(
            card=card,
            category="delivery",
            discount_type=DiscountType.RATE,
            discount_rate="0.05",
            merchant_scope=["배달의민족", "요기요"],
            raw_text="배달의민족, 요기요 5% 할인",
            parse_status=ParseStatus.REVIEW_REQUIRED,
        )

        decision = evaluate_card_gorilla_activation(card)

        blockers = next(iter(decision.blocked_benefits.values()), [])
        self.assertNotIn("merchant_scope_required", blockers)

    def test_parsed_channel_does_not_block_activation(self):
        card = self.create_card()
        BenefitRule.objects.create(
            card=card,
            category="delivery",
            discount_type=DiscountType.RATE,
            discount_rate="0.05",
            merchant_scope=["배달의민족"],
            channel="online",
            raw_text="배달의민족 공식 홈페이지 온라인 결제 5% 할인",
            parse_status=ParseStatus.REVIEW_REQUIRED,
        )

        decision = evaluate_card_gorilla_activation(card)

        blockers = next(iter(decision.blocked_benefits.values()), [])
        self.assertNotIn("channel_unparsed", blockers)

    def test_payment_method_condition_can_activate_as_display_only(self):
        card = self.create_card()
        BenefitRule.objects.create(
            card=card,
            category="convenience",
            discount_type=DiscountType.RATE,
            discount_rate="0.05",
            merchant_scope=["CU"],
            channel="offline",
            raw_text="CU 오프라인 바코드 결제 5% 할인",
            parse_status=ParseStatus.REVIEW_REQUIRED,
            unsupported_conditions=["payment_method_condition"],
        )

        decision = evaluate_card_gorilla_activation(card)

        self.assertTrue(decision.can_activate)
        self.assertTrue(apply_card_gorilla_activation(card, decision))
        benefit = card.benefits.get()
        self.assertEqual(benefit.parse_status, ParseStatus.ACTIVE)
        self.assertEqual(
            benefit.unsupported_conditions,
            ["payment_method_condition"],
        )

    def test_universal_category_benefit_can_activate_despite_standard_exclusions(self):
        card = self.create_card()
        BenefitRule.objects.create(
            card=card,
            category="cafe",
            discount_type=DiscountType.RATE,
            discount_rate="0.003",
            raw_text="국내 전 가맹점 0.3% 캐시백 - 상품권/선불카드 제외",
            parse_status=ParseStatus.REVIEW_REQUIRED,
            unsupported_conditions=["source_review_required"],
        )

        decision = evaluate_card_gorilla_activation(card)

        self.assertTrue(decision.can_activate)

    def test_statement_period_tilde_is_not_variable_rate(self):
        card = self.create_card()
        benefit = BenefitRule.objects.create(
            card=card,
            category="delivery",
            discount_type=DiscountType.RATE,
            discount_rate=Decimal("0.1"),
            minimum_transaction_amount=20000,
            category_monthly_limit=5000,
            merchant_scope=["배달의민족"],
            raw_text=(
                "배달의민족 10% 할인, 지난달 1일 ~ 말일까지 "
                "50만원 이상 이용 시 제공"
            ),
            parse_status=ParseStatus.REVIEW_REQUIRED,
            unsupported_conditions=["source_review_required"],
        )

        blockers = evaluate_benefit_for_activation(benefit)

        self.assertNotIn("variable_rate", blockers)
        self.assertEqual(blockers, [])

    def test_payment_method_condition_is_preserved_as_display_only(self):
        card = self.create_card()
        benefit = BenefitRule.objects.create(
            card=card,
            category="shopping",
            discount_type=DiscountType.RATE,
            discount_rate=Decimal("0.1"),
            minimum_transaction_amount=20000,
            category_monthly_limit=5000,
            raw_text="모든 간편결제 이용금액은 혜택이 제공되지 않습니다.",
            parse_status=ParseStatus.REVIEW_REQUIRED,
            unsupported_conditions=["source_review_required"],
        )

        blockers = evaluate_benefit_for_activation(benefit)

        self.assertNotIn("payment_method_condition", blockers)
        self.assertIn(
            "payment_method_condition",
            collect_display_only_conditions(benefit),
        )
