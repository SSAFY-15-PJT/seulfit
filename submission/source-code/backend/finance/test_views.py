from django.test import TestCase
from rest_framework.test import APIClient

from finance.models import (
    BenefitRule,
    CardProduct,
    CardType,
    DiscountType,
    ParseStatus,
)


class CardProductListApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        for status in (ParseStatus.ACTIVE, ParseStatus.REVIEW_REQUIRED):
            card = CardProduct.objects.create(
                external_id=f"card-{status}",
                issuer="테스트카드",
                provider="테스트카드",
                source_channel="test",
                card_type=CardType.CREDIT,
                name=f"{status} 카드",
                source_url=f"https://example.com/{status}",
                annual_fee=10000 if status == ParseStatus.ACTIVE else None,
                parse_status=status,
                raw_text="원문",
            )
            BenefitRule.objects.create(
                card=card,
                category="cafe",
                discount_type=DiscountType.RATE,
                discount_rate="0.1",
                raw_text="카페 10% 할인",
                parse_status=status,
                unsupported_conditions=(
                    ["merchant_scope"]
                    if status == ParseStatus.REVIEW_REQUIRED
                    else []
                ),
            )

    def test_status_filter_returns_sqlite_cards(self):
        response = self.client.get(
            "/api/v1/finance/cards/",
            {"status": ParseStatus.REVIEW_REQUIRED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["parse_status"],
            ParseStatus.REVIEW_REQUIRED,
        )
        self.assertEqual(
            response.data["results"][0]["benefits"][0]["parse_status"],
            ParseStatus.REVIEW_REQUIRED,
        )
