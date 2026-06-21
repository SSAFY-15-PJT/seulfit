from decimal import Decimal

from rest_framework.test import APITestCase

from finance.models import (
    BenefitRule,
    CardProduct,
    CardType,
    DiscountType,
    ParseStatus,
)


class SimulateApiTests(APITestCase):
    url = "/api/v1/hyperlocal/simulate/"

    def create_card(self, parse_status=ParseStatus.ACTIVE):
        card = CardProduct.objects.create(
            external_id=f"card-{parse_status}",
            issuer="테스트카드",
            provider="테스트카드",
            source_channel="test",
            card_type=CardType.CREDIT,
            name=f"{parse_status} 카드",
            source_url=f"https://example.com/{parse_status}",
            annual_fee=12000 if parse_status == ParseStatus.ACTIVE else None,
            previous_month_requirement=0,
            monthly_discount_limit=30000,
            parse_status=parse_status,
            raw_text="카드 원문",
        )
        BenefitRule.objects.create(
            card=card,
            category="cafe",
            discount_type=DiscountType.RATE,
            discount_rate=Decimal("0.1"),
            raw_text="카페 10% 할인",
            parse_status=(
                ParseStatus.ACTIVE
                if parse_status == ParseStatus.ACTIVE
                else ParseStatus.REVIEW_REQUIRED
            ),
        )
        return card

    def test_no_active_cards_returns_explicit_empty_state(self):
        self.create_card(ParseStatus.REVIEW_REQUIRED)

        response = self.client.post(
            self.url,
            {"spending": {"cafe": 100000}},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["recommendation_source"], "sqlite")
        self.assertEqual(response.data["candidate_count"], 0)
        self.assertEqual(response.data["excluded_review_count"], 1)
        self.assertEqual(response.data["fallback_reason"], "no_active_cards")
        self.assertEqual(response.data["card_ranking_list"], [])
        self.assertIsNone(response.data["best_card"])

    def test_active_card_is_ranked_from_sqlite(self):
        card = self.create_card(ParseStatus.ACTIVE)

        response = self.client.post(
            self.url,
            {
                "spending": {"cafe": 100000},
                "previous_month_spending": 100000,
                "owned_card_ids": [card.pk],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["recommendation_source"], "sqlite")
        self.assertEqual(response.data["candidate_count"], 1)
        self.assertEqual(response.data["best_card"]["id"], card.pk)
        self.assertEqual(
            response.data["best_card"]["estimated_net_value"],
            9000,
        )
        self.assertTrue(response.data["best_card"]["is_owned"])

    def test_api_applies_merchant_scope_from_sqlite(self):
        card = self.create_card(ParseStatus.ACTIVE)
        benefit = card.benefits.get()
        benefit.merchant_scope = ["스타벅스"]
        benefit.save(update_fields=["merchant_scope", "updated_at"])

        response = self.client.post(
            self.url,
            {
                "spending": {"cafe": 30000},
                "transactions": [
                    {
                        "category": "cafe",
                        "merchant_name": "스타벅스 강남역점",
                        "amount": 10000,
                    },
                    {
                        "category": "cafe",
                        "merchant_name": "동네커피",
                        "amount": 20000,
                    },
                ],
            },
            format="json",
        )

        detail = response.data["best_card"]["calculation_breakdown"][0]
        self.assertEqual(response.data["best_card"]["estimated_gross_benefit"], 1000)
        self.assertEqual(detail["matched_transaction_count"], 1)
        self.assertEqual(detail["excluded_transaction_count"], 1)

    def test_mock_fallback_requires_explicit_flag(self):
        response = self.client.post(
            self.url,
            {
                "spending": {"cafe": 100000},
                "previous_month_spending": 400000,
                "allow_mock_fallback": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["recommendation_source"],
            "mock_fallback",
        )
        self.assertEqual(response.data["candidate_count"], 3)
        self.assertEqual(len(response.data["card_ranking_list"]), 3)
