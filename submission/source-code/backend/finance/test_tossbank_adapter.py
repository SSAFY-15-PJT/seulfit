from email.message import Message
from io import BytesIO

from django.test import SimpleTestCase

from finance.adapters.tossbank import TossBankAdapter


class FakeResponse(BytesIO):
    def __init__(self, content, content_type="text/html; charset=utf-8"):
        super().__init__(content.encode("utf-8"))
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class TossBankAdapterTests(SimpleTestCase):
    def test_discovery_uses_five_official_product_urls(self):
        def opener(request, timeout):
            return FakeResponse(
                "User-agent: *\nAllow: /\n",
                "text/plain",
            )

        items = TossBankAdapter(opener=opener).discover_items()

        self.assertEqual(len(items), 5)
        self.assertEqual(items[0]["external_id"], "check-card")
        self.assertEqual(items[-1]["external_id"], "wide-card")

    def test_parser_extracts_metadata_and_uses_verified_day_rules(self):
        html = """
        <meta property="og:title" content="토스뱅크 데이카드 | 토스뱅크">
        <meta property="og:image" content="https://example.com/card.png">
        <div>전월 이용실적 30만원 이상 카페 이용금액 10% 캐시백</div>
        """

        parsed = TossBankAdapter().parse_product(
            "https://www.tossbank.com/product-service/card/day-card",
            html,
        )

        self.assertEqual(parsed["name"], "토스뱅크 데이카드")
        self.assertEqual(parsed["annual_fee"], 20000)
        self.assertEqual(parsed["card_type"], "credit")
        self.assertEqual(parsed["issuer"], "하나카드")
        self.assertEqual(parsed["previous_month_requirement"], 300000)
        self.assertEqual(parsed["benefits"][0]["category"], "cafe")
        self.assertEqual(
            parsed["benefits"][0]["unsupported_conditions"],
            [],
        )

    def test_specialized_cards_use_supported_conservative_rates(self):
        business = TossBankAdapter._specialized_benefits(
            "individual-business-card"
        )
        wide = TossBankAdapter._specialized_benefits("wide-card")

        self.assertEqual(len(business), 6)
        self.assertEqual(business[0]["discount_rate"], "0.003")
        self.assertEqual(wide[0]["discount_rate"], "0.01")
        self.assertIsNone(wide[0]["category_monthly_limit"])

    def test_moim_card_uses_conservative_supported_cashback_rules(self):
        benefits = TossBankAdapter._specialized_benefits("moim-card")

        self.assertEqual(
            {item["category"] for item in benefits},
            {"mart", "food"},
        )
        self.assertTrue(
            all(
                item["discount_amount"] == 500
                and item["minimum_transaction_amount"] == 10000
                and item["daily_usage_limit"] == 1
                and item["monthly_usage_limit"] == 5
                and item["category_monthly_limit"] == 2500
                for item in benefits
            )
        )
        food = next(item for item in benefits if item["category"] == "food")
        self.assertEqual((food["start_hour"], food["end_hour"]), (19, 24))

    def test_day_card_models_supported_areas_and_limits(self):
        parsed = TossBankAdapter().parse_product(
            "https://www.tossbank.com/product-service/card/day-card",
            '<meta property="og:title" content="토스뱅크 데이카드">',
        )

        self.assertEqual(
            {item["category"] for item in parsed["benefits"]},
            {"cafe", "mart", "shopping"},
        )
        self.assertEqual(
            [tier["monthly_discount_limit"] for tier in parsed["benefit_tiers"]],
            [30000, 50000],
        )
        self.assertEqual(
            [
                tier["monthly_discount_limit"]
                for tier in parsed["service_limit_tiers"]
                if tier["benefit_group"] == "day_cafe"
            ],
            [5000, 10000],
        )
