import json
from email.message import Message
from io import BytesIO

from django.test import SimpleTestCase

from finance.adapters.wooricard import WooriCardAdapter


class FakeResponse(BytesIO):
    def __init__(self, content, content_type="text/html; charset=utf-8"):
        super().__init__(content.encode("utf-8"))
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class WooriCardAdapterTests(SimpleTestCase):
    def test_discovery_reads_official_sitemap_and_applies_limit(self):
        sitemap = """
        <urlset>
          <url><loc>https://m.wooricard.com/ai-data/card_100.html</loc></url>
          <url><loc>https://m.wooricard.com/ai-data/card_200.html</loc></url>
        </urlset>
        """

        def opener(request, timeout):
            if request.full_url.endswith("/robots.txt"):
                return FakeResponse(
                    "User-agent: *\nAllow: /ai-data/\n",
                    "text/plain",
                )
            return FakeResponse(sitemap, "application/xml; charset=utf-8")

        items = WooriCardAdapter(opener=opener).discover_items(limit=1)

        self.assertEqual(
            items,
            [
                {
                    "external_id": "100",
                    "source_url": (
                        "https://m.wooricard.com/ai-data/card_100.html"
                    ),
                }
            ],
        )

    def test_parser_extracts_json_ld_fee_image_and_review_benefit(self):
        payload = {
            "@context": "https://schema.org",
            "@type": "CreditCard",
            "name": "테스트 우리카드",
            "image": "https://example.com/card.png",
            "annualFee": "연회비 18,000원 20,000원",
        }
        html = f"""
        <script type="application/ld+json">
        {json.dumps(payload, ensure_ascii=False)}
        </script>
        <div>카드 종류 신용카드 전월 이용실적 30만원 이상</div>
        <h3>카페 할인</h3>
        <p>스타벅스 이용금액 10% 청구할인</p>
        """

        parsed = WooriCardAdapter().parse_product(
            "https://m.wooricard.com/ai-data/card_100.html",
            html,
        )

        self.assertEqual(parsed["name"], "테스트 우리카드")
        self.assertEqual(parsed["annual_fee"], 18000)
        self.assertEqual(parsed["previous_month_requirement"], 300000)
        self.assertEqual(parsed["benefits"][0]["category"], "cafe")
        self.assertEqual(parsed["benefits"][0]["discount_rate"], "0.1")
        self.assertIn(
            "source_review_required",
            parsed["benefits"][0]["unsupported_conditions"],
        )

    def test_specialized_cards_use_conservative_supported_rules(self):
        for name, expected_rate in (
            ("NU Biz", "0.005"),
            ("KREAM 우리카드", "0.005"),
            ("DA카드의정석 Ⅱ", "0.008"),
            ("카드의정석 I&U+", "0.007"),
            ("카드의정석2 EVERY POINT", "0.008"),
            ("트래블월렛 우리카드", "0.01"),
        ):
            with self.subTest(name=name):
                benefits = WooriCardAdapter._specialized_benefits(name)
                self.assertEqual(len(benefits), 6)
                self.assertEqual(benefits[0]["discount_rate"], expected_rate)
                self.assertEqual(benefits[0]["unsupported_conditions"], [])

        lg_tiers = WooriCardAdapter._specialized_service_limit_tiers(
            "LG전자 우리카드"
        )
        self.assertEqual(
            [tier["monthly_discount_limit"] for tier in lg_tiers],
            [10000, 15000, 20000],
        )

    def test_card_type_ignores_check_word_in_terms(self):
        html = """
        <script type="application/ld+json">
        {
          "@type": "CreditCard",
          "name": "카드의정석 SHOPPING+",
          "annualFee": "10,000원"
        }
        </script>
        <div>카드 종류 신용카드</div>
        <p>체크카드 결제서비스 이용 시 일부 혜택 제외</p>
        """

        parsed = WooriCardAdapter().parse_product(
            "https://m.wooricard.com/ai-data/card_102492.html",
            html,
        )

        self.assertEqual(parsed["card_type"], "credit")

    def test_check_card_name_takes_priority_over_page_label(self):
        self.assertEqual(
            WooriCardAdapter._card_type(
                "카드의정석 오하CHECK",
                "카드 종류 신용카드",
            ),
            "debit",
        )

    def test_shopping_plus_uses_verified_offline_limits(self):
        benefits = WooriCardAdapter._specialized_benefits(
            "카드의정석 SHOPPING+"
        )
        tiers = WooriCardAdapter._specialized_service_limit_tiers(
            "카드의정석 SHOPPING+"
        )

        self.assertEqual(
            {benefit["category"] for benefit in benefits},
            {"mart", "convenience", "shopping"},
        )
        self.assertTrue(
            all(
                benefit["discount_rate"] == "0.10"
                and benefit["per_transaction_limit"] == 5000
                and benefit["channel"] == "offline"
                for benefit in benefits
            )
        )
        self.assertEqual(
            [tier["monthly_discount_limit"] for tier in tiers],
            [6000, 12000, 24000],
        )

    def test_oha_check_uses_supported_shopping_and_eat_groups(self):
        benefits = WooriCardAdapter._specialized_benefits(
            "카드의정석 오하CHECK"
        )
        tiers = WooriCardAdapter._specialized_service_limit_tiers(
            "카드의정석 오하CHECK"
        )

        self.assertEqual(
            {(benefit["category"], benefit["benefit_group"]) for benefit in benefits},
            {
                ("shopping", "oha_shopping"),
                ("cafe", "oha_eat"),
                ("food", "oha_eat"),
            },
        )
        self.assertTrue(
            all(
                benefit["discount_rate"] == "0.05"
                and benefit["per_transaction_limit"] == 1000
                for benefit in benefits
            )
        )
        self.assertEqual(len(tiers), 6)
        self.assertEqual(
            [
                tier["monthly_discount_limit"]
                for tier in tiers
                if tier["benefit_group"] == "oha_eat"
            ],
            [2000, 4000, 6000],
        )

    def test_kaltoe_check_uses_time_usage_and_tier_limits(self):
        benefits = WooriCardAdapter._specialized_benefits(
            "카드의정석2 칼퇴 CHECK"
        )
        tiers = WooriCardAdapter._specialized_service_limit_tiers(
            "카드의정석2 칼퇴 CHECK"
        )

        self.assertEqual(
            {benefit["category"] for benefit in benefits},
            {"food", "cafe", "convenience"},
        )
        self.assertTrue(
            all(
                benefit["start_hour"] == 18
                and benefit["end_hour"] == 23
                and benefit["daily_usage_limit"] == 1
                for benefit in benefits
            )
        )
        self.assertEqual(
            [tier["monthly_discount_limit"] for tier in tiers],
            [4000, 8000, 15000],
        )

    def test_happy_cards_use_supported_shopping_life_group(self):
        for name, rate, transaction_limit in (
            ("국민행복카드S2", "0.05", 2500),
            ("국민행복 체크카드S2", "0.02", 10000),
        ):
            with self.subTest(name=name):
                benefits = WooriCardAdapter._specialized_benefits(name)
                tiers = WooriCardAdapter._specialized_service_limit_tiers(name)

                self.assertEqual(
                    {(item["category"], item["channel"]) for item in benefits},
                    {
                        ("mart", "offline"),
                        ("shopping", "offline"),
                        ("shopping", "online"),
                    },
                )
                self.assertTrue(
                    all(
                        item["discount_rate"] == rate
                        and item["per_transaction_limit"]
                        == transaction_limit
                        for item in benefits
                    )
                )
                self.assertEqual(
                    [tier["monthly_discount_limit"] for tier in tiers],
                    [4000, 8000, 16000],
                )

    def test_gs_freight_card_excludes_fuel_and_models_lifestyle_limits(self):
        benefits = WooriCardAdapter._specialized_benefits(
            "GS칼텍스 화물복지카드"
        )
        tiers = WooriCardAdapter._specialized_service_limit_tiers(
            "GS칼텍스 화물복지카드"
        )

        self.assertEqual(
            {item["category"] for item in benefits},
            {"mart", "cafe"},
        )
        self.assertEqual(
            {
                item["category"]: (
                    item["daily_usage_limit"],
                    item["monthly_usage_limit"],
                )
                for item in benefits
            },
            {"mart": (1, 3), "cafe": (1, 2)},
        )
        self.assertEqual(
            [
                tier["monthly_discount_limit"]
                for tier in tiers
                if tier["benefit_group"] == "gs_freight_mart"
            ],
            [5000, 10000],
        )
