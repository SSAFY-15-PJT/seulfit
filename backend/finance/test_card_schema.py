from decimal import Decimal

from django.test import SimpleTestCase

from finance.card_schema import (
    validate_benefit_rule,
    validate_benefit_tier,
    validate_service_limit_tier,
    validate_card_product,
)
from finance.models import ParseStatus


class CardSchemaTests(SimpleTestCase):
    def test_valid_service_limit_tier_is_validated(self):
        result = validate_service_limit_tier(
            {
                "benefit_group": "life_service",
                "minimum_spending": 300000,
                "maximum_spending": 700000,
                "monthly_spending_limit": 150000,
                "monthly_discount_limit": 7500,
                "monthly_usage_limit": None,
                "raw_text": "30만원 이상 생활서비스 15만원",
            }
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.parse_status, ParseStatus.VALIDATED)

    def test_valid_benefit_tier_is_validated(self):
        result = validate_benefit_tier(
            {
                "scope": "card_total",
                "minimum_spending": 400000,
                "maximum_spending": 800000,
                "monthly_discount_limit": 30000,
                "raw_text": "40만원 이상 80만원 미만 3만원",
            }
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.parse_status, ParseStatus.VALIDATED)

    def test_invalid_benefit_tier_range_is_rejected(self):
        result = validate_benefit_tier(
            {
                "scope": "card_total",
                "minimum_spending": 800000,
                "maximum_spending": 400000,
                "monthly_discount_limit": 30000,
                "raw_text": "잘못된 구간",
            }
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(result.parse_status, ParseStatus.INVALID)

    def test_valid_rate_benefit_is_active(self):
        result = validate_benefit_rule(
            {
                "category": "cafe",
                "discount_type": "rate",
                "discount_rate": "0.1",
                "discount_amount": None,
                "minimum_transaction_amount": 5000,
                "raw_text": "커피 10% 할인",
            }
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.parse_status, ParseStatus.ACTIVE)
        self.assertEqual(
            result.normalized_data["discount_rate"],
            Decimal("0.1"),
        )

    def test_daily_usage_limit_is_supported(self):
        result = validate_benefit_rule(
            {
                "category": "cafe",
                "discount_type": "rate",
                "discount_rate": "0.1",
                "discount_amount": None,
                "minimum_transaction_amount": 0,
                "daily_usage_limit": 1,
                "raw_text": "일 1회 커피 10% 할인",
            }
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.parse_status, ParseStatus.ACTIVE)
        self.assertEqual(result.normalized_data["daily_usage_limit"], 1)

    def test_concrete_merchant_scope_is_supported(self):
        result = validate_benefit_rule(
            {
                "category": "cafe",
                "discount_type": "rate",
                "discount_rate": "0.05",
                "discount_amount": None,
                "minimum_transaction_amount": 0,
                "merchant_scope": ["스타벅스", "이디야"],
                "raw_text": "스타벅스, 이디야 5% 할인",
                "unsupported_conditions": ["merchant_scope"],
            }
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.parse_status, ParseStatus.ACTIVE)
        self.assertNotIn(
            "merchant_scope",
            result.normalized_data["unsupported_conditions"],
        )

    def test_unmapped_category_marker_requires_review(self):
        result = validate_benefit_rule(
            {
                "category": "etc",
                "discount_type": "rate",
                "discount_rate": "0.1",
                "discount_amount": None,
                "minimum_transaction_amount": 0,
                "raw_text": "자동 분류하지 못한 혜택",
                "unsupported_conditions": ["category_mapping"],
            }
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.parse_status, ParseStatus.REVIEW_REQUIRED)

    def test_conflicting_discount_fields_are_invalid(self):
        result = validate_benefit_rule(
            {
                "category": "cafe",
                "discount_type": "rate",
                "discount_rate": "0.1",
                "discount_amount": 1000,
                "minimum_transaction_amount": 0,
                "raw_text": "혜택",
            }
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(result.parse_status, ParseStatus.INVALID)

    def test_unmapped_usage_limit_requires_review(self):
        result = validate_benefit_rule(
            {
                "category": "convenience",
                "discount_type": "amount",
                "discount_amount": 2500,
                "minimum_transaction_amount": 0,
                "monthly_usage_limit": None,
                "raw_text": "건당 2,500원, 월 최대 6회 할인",
            }
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.parse_status, ParseStatus.REVIEW_REQUIRED)
        self.assertIn(
            "usage_limit_mapping",
            result.normalized_data["unsupported_conditions"],
        )

    def test_card_without_structured_benefits_requires_review(self):
        result = validate_card_product(
            {
                "external_id": "card-1",
                "issuer": "카드사",
                "provider": "카드사",
                "source_channel": "issuer",
                "card_type": "credit",
                "name": "카드",
                "source_url": "https://example.com/card",
                "annual_fee": 10000,
                "previous_month_requirement": 300000,
                "monthly_discount_limit": None,
                "raw_text": "원문",
                "benefits": [],
            }
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.parse_status, ParseStatus.REVIEW_REQUIRED)

    def test_unknown_category_is_invalid(self):
        result = validate_card_product(
            {
                "external_id": "card-1",
                "issuer": "카드사",
                "provider": "카드사",
                "source_channel": "issuer",
                "card_type": "credit",
                "name": "카드",
                "source_url": "https://example.com/card",
                "annual_fee": 10000,
                "previous_month_requirement": 0,
                "monthly_discount_limit": None,
                "raw_text": "원문",
                "benefits": [
                    {
                        "category": "unknown",
                        "discount_type": "rate",
                        "discount_rate": "0.1",
                        "discount_amount": None,
                        "minimum_transaction_amount": 0,
                        "raw_text": "혜택",
                    }
                ],
            }
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(result.parse_status, ParseStatus.INVALID)

    def test_check_card_name_conflicting_with_credit_type_is_invalid(self):
        result = validate_card_product(
            {
                "external_id": "check-card",
                "issuer": "카드사",
                "provider": "카드사",
                "source_channel": "issuer",
                "card_type": "credit",
                "name": "생활 CHECK 카드",
                "source_url": "https://example.com/check-card",
                "annual_fee": 0,
                "previous_month_requirement": 0,
                "monthly_discount_limit": None,
                "raw_text": "체크카드 상품 설명",
                "benefits": [
                    {
                        "category": "cafe",
                        "discount_type": "rate",
                        "discount_rate": "0.01",
                        "discount_amount": None,
                        "minimum_transaction_amount": 0,
                        "raw_text": "카페 1% 적립",
                    }
                ],
            }
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(result.parse_status, ParseStatus.INVALID)
        self.assertIn(
            "card_type: 카드명의 체크카드 표기와 충돌함",
            result.errors,
        )
