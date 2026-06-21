import json
from email.message import Message
from io import BytesIO

from django.test import SimpleTestCase

from finance.adapters.shinhan import ShinhanAdapter


class FakeResponse(BytesIO):
    def __init__(self, content, content_type="text/html; charset=utf-8"):
        super().__init__(content.encode("utf-8"))
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class ShinhanAdapterTests(SimpleTestCase):
    def test_discovery_reads_official_item_list_and_applies_limit(self):
        listing = """
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "ItemList",
          "itemListElement": [
            {
              "item": {
                "@type": "Product",
                "name": "Card A",
                "image": "https://cdn.example/a.webp",
                "url": "https://www.shinhancard.com/pconts/html/card/apply/credit/1_2207.html"
              }
            },
            {
              "item": {
                "@type": "Product",
                "name": "Card B",
                "image": "https://cdn.example/b.webp",
                "url": "https://www.shinhancard.com/pconts/html/card/apply/credit/2_2207.html"
              }
            }
          ]
        }
        </script>
        """

        def opener(request, timeout):
            if request.full_url.endswith("/robots.txt"):
                return FakeResponse(
                    "User-agent: *\nAllow: /pconts/html/card/\n",
                    "text/plain",
                )
            return FakeResponse(listing)

        items = ShinhanAdapter(opener=opener).discover_items(limit=1)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["external_id"], "1_2207")
        self.assertEqual(items[0]["name"], "Card A")

    def test_discovery_uses_official_api_and_paginates_to_limit(self):
        robots = "User-agent: *\nAllow: /pconts/html/card/\n"

        def api_payload(index):
            start = (index - 1) * 8
            cards = [
                {
                    "cardProductEntryId": str(1000 + number),
                    "cardProductEntryName": f"Card {number}",
                    "cardProductUrl": (
                        "/pconts/html/card/apply/credit/"
                        f"{number}_2207.html"
                    ),
                    "thumbnailImgUrl": f"/images/{number}.webp",
                    "afeAmountOrigin": 10000 + number,
                }
                for number in range(start + 1, start + 9)
            ]
            return json.dumps(
                {
                    "status": 200,
                    "payload": {
                        "totalPage": 2,
                        "cardInformationList": cards,
                    },
                }
            )

        def opener(request, timeout):
            if request.full_url.endswith("/robots.txt"):
                return FakeResponse(robots, "text/plain")
            index = 2 if "index=2" in request.full_url else 1
            return FakeResponse(
                api_payload(index),
                "application/json; charset=utf-8",
            )

        items = ShinhanAdapter(opener=opener).discover_items(limit=15)

        self.assertEqual(len(items), 15)
        self.assertEqual(items[0]["external_id"], "1_2207")
        self.assertEqual(items[-1]["external_id"], "15_2207")
        self.assertEqual(items[0]["annual_fee"], 10001)
        self.assertIn("entryId=1001", items[0]["annual_fee_source_url"])

    def test_detail_parser_uses_discovered_official_annual_fee(self):
        parsed = ShinhanAdapter().parse_product(
            "https://www.shinhancard.com/pconts/html/card/apply/credit/"
            "123_2207.html",
            '<meta property="og:title" content="신한카드 테스트">',
            discovered={
                "annual_fee": 17000,
                "annual_fee_source_url": "https://shapi.example/detail",
            },
        )

        self.assertEqual(parsed["annual_fee"], 17000)
        self.assertEqual(
            parsed["annual_fee_source_url"],
            "https://shapi.example/detail",
        )
        self.assertFalse(
            any("연회비" in reason for reason in parsed["review_reasons"])
        )

    def test_simple_plan_plus_uses_supported_domestic_rate_rules(self):
        parsed = ShinhanAdapter().parse_product(
            "https://www.shinhancard.com/pconts/html/card/apply/credit/"
            "1237252_2207.html",
            '<meta property="og:title" content="신한카드 Simple Plan+">',
            discovered={"annual_fee": 47000},
        )

        self.assertEqual(len(parsed["benefits"]), 6)
        self.assertEqual(
            {benefit["discount_rate"] for benefit in parsed["benefits"]},
            {"0.015"},
        )

    def test_specialized_cards_include_verified_limits_and_scopes(self):
        cases = {
            "배민 신한카드 밥친구": ("food", ["배달의민족"], 30000),
            "알리익스프레스 신한카드": (
                "shopping",
                ["알리익스프레스"],
                None,
            ),
            "신한카드 Edu Plan+": (
                "mart",
                ["홈플러스", "이마트", "롯데마트"],
                None,
            ),
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                parsed = ShinhanAdapter().parse_product(
                    "https://www.shinhancard.com/pconts/html/card/apply/credit/"
                    "card_2207.html",
                    f'<meta property="og:title" content="{name}">',
                    discovered={"annual_fee": 10000},
                )
                benefit = parsed["benefits"][0]
                self.assertEqual(benefit["category"], expected[0])
                self.assertEqual(benefit["merchant_scope"], expected[1])
                self.assertEqual(
                    benefit["category_monthly_limit"],
                    expected[2],
                )

        ali = ShinhanAdapter().parse_product(
            "https://www.shinhancard.com/pconts/html/card/apply/credit/"
            "ali_2207.html",
            '<meta property="og:title" content="알리익스프레스 신한카드">',
            discovered={"annual_fee": 16000},
        )
        self.assertEqual(
            [
                tier["monthly_discount_limit"]
                for tier in ali["service_limit_tiers"]
            ],
            [10000, 20000, 30000],
        )

    def test_unboxing_uses_transaction_and_spending_tier_limits(self):
        parsed = ShinhanAdapter().parse_product(
            "https://www.shinhancard.com/pconts/html/card/apply/credit/"
            "1198302_2207.html",
            '<meta property="og:title" content="신한카드 Unboxing">',
            discovered={"annual_fee": 32000},
        )

        self.assertEqual(parsed["previous_month_requirement"], 400000)
        special = next(
            benefit
            for benefit in parsed["benefits"]
            if benefit["benefit_group"] == "unboxing_special"
        )
        self.assertEqual(special["discount_amount"], 2500)
        self.assertEqual(special["maximum_transaction_amount"], 30000)
        self.assertEqual(special["monthly_usage_limit"], 6)
        self.assertEqual(
            [
                (
                    tier["minimum_spending"],
                    tier["monthly_discount_limit"],
                    tier["monthly_usage_limit"],
                )
                for tier in parsed["service_limit_tiers"]
                if tier["benefit_group"] == "unboxing_special"
            ],
            [
                (400000, 5000, 2),
                (800000, 10000, 4),
                (1200000, 15000, 6),
            ],
        )

    def test_first_card_splits_categories_and_daily_limit(self):
        parsed = ShinhanAdapter().parse_product(
            "https://www.shinhancard.com/pconts/html/card/apply/credit/"
            "1229296_2207.html",
            '<meta property="og:title" content="신한카드 처음">',
            discovered={"annual_fee": 0},
        )

        self.assertEqual(
            {benefit["category"] for benefit in parsed["benefits"]},
            {"food", "cafe", "convenience", "shopping"},
        )
        self.assertTrue(
            all(
                benefit["per_transaction_limit"] == 500
                and benefit["daily_benefit_limit"] == 1000
                for benefit in parsed["benefits"]
            )
        )
        self.assertEqual(
            [
                tier["monthly_discount_limit"]
                for tier in parsed["service_limit_tiers"]
            ],
            [5000, 10000, 20000],
        )

    def test_lg_subscription_card_models_discount_and_point_groups(self):
        parsed = ShinhanAdapter().parse_product(
            "https://www.shinhancard.com/pconts/html/card/apply/credit/"
            "1234346_2207.html",
            '<meta property="og:title" content="LG전자 The 구독케어 신한카드">',
            discovered={"annual_fee": 22000},
        )

        self.assertEqual(
            {item["benefit_group"] for item in parsed["benefits"]},
            {"lg_subscription_discount", "lg_subscription_point"},
        )
        point = next(
            item
            for item in parsed["benefits"]
            if item["benefit_group"] == "lg_subscription_point"
        )
        self.assertEqual(point["minimum_transaction_amount"], 70000)
        self.assertEqual(
            [
                tier["monthly_discount_limit"]
                for tier in parsed["service_limit_tiers"]
                if tier["benefit_group"] == "lg_subscription_discount"
            ],
            [13000, 16000, 20000],
        )

    def test_kpass_models_supported_lifestyle_benefits(self):
        parsed = ShinhanAdapter().parse_product(
            "https://www.shinhancard.com/pconts/html/card/apply/credit/"
            "1225543_2207.html",
            '<meta property="og:title" content="K-패스 신한카드">',
            discovered={"annual_fee": 7000},
        )

        self.assertEqual(parsed["previous_month_requirement"], 300000)
        self.assertEqual(
            {item["category"] for item in parsed["benefits"]},
            {"food", "convenience", "cafe", "shopping"},
        )
        self.assertTrue(
            all(
                item["minimum_transaction_amount"] == 20000
                and item["per_transaction_limit"] == 3000
                and item["daily_usage_limit"] == 1
                for item in parsed["benefits"]
            )
        )
        self.assertEqual(
            [
                tier["monthly_discount_limit"]
                for tier in parsed["service_limit_tiers"]
            ],
            [7000, 15000],
        )

    def test_older_first_card_design_is_marked_inactive(self):
        parsed = ShinhanAdapter().parse_product(
            "https://www.shinhancard.com/pconts/html/card/apply/credit/"
            "1227020_2207.html",
            '<meta property="og:title" content="신한카드 처음">',
            discovered={"annual_fee": 0},
        )

        self.assertEqual(parsed["parse_status_override"], "inactive")
        self.assertTrue(
            any("구형 디자인" in reason for reason in parsed["review_reasons"])
        )

    def test_detail_parser_extracts_product_benefits_and_images(self):
        html = """
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "신한카드 테스트",
          "description": "생활 할인",
          "offers": {"url": "https://example.com"}
        }
        </script>
        <h4>편의점 5% 할인</h4>
        <p>전월 이용금액 30만원 이상 오프라인 가맹점에서 제공합니다.</p>
        <h4>영화서비스 5천원 할인</h4>
        <p>월 1회 제공됩니다.</p>
        <script>
          const cardPlate = [{
            img: {
              front: {
                webp: "/static/images/card/plate/TEST_v_f_d.webp",
                img: "/static/images/card/plate/TEST_v_f_d.png"
              }
            }
          }];
        </script>
        """
        url = (
            "https://www.shinhancard.com/pconts/html/card/apply/credit/"
            "123_2207.html"
        )

        parsed = ShinhanAdapter().parse_product(url, html)

        self.assertEqual(parsed["name"], "신한카드 테스트")
        self.assertEqual(parsed["previous_month_requirement"], 300000)
        self.assertEqual(parsed["benefits"][0]["category"], "convenience")
        self.assertEqual(parsed["benefits"][0]["discount_rate"], "0.05")
        self.assertIn(
            "https://cdn.www.shinhancard.com/pconts/static/images/card/plate/"
            "TEST_v_f_d.webp",
            {image["source_url"] for image in parsed["images"]},
        )
        self.assertIn("연회비", parsed["review_reasons"][0])

    def test_detail_parser_does_not_guess_missing_annual_fee(self):
        parsed = ShinhanAdapter().parse_product(
            "https://www.shinhancard.com/pconts/html/card/apply/credit/"
            "123_2207.html",
            '<meta property="og:title" content="신한카드 테스트">',
        )

        self.assertIsNone(parsed["annual_fee"])
        self.assertTrue(
            any("연회비" in reason for reason in parsed["review_reasons"])
        )

    def test_detail_parser_extracts_total_discount_tiers(self):
        html = """
        <h4>서비스별 월 통합 혜택 한도</h4>
        <table>
          <thead>
            <tr>
              <th colspan="2">전월 이용금액</th>
              <th>40만원 이상<br>80만원 미만</th>
              <th>80만원 이상<br>120만원 미만</th>
              <th>120만원 이상<br>180만원 미만</th>
              <th>180만원 이상</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colspan="2">월 최대 혜택 한도</td>
              <td>3만원</td>
              <td>5만원</td>
              <td>7만 3천원</td>
              <td>10만원</td>
            </tr>
          </tbody>
        </table>
        <p>
          전월 이용금액 120만원 이상 150만원 미만일 경우 최대 7만원,
          150만원 이상 180만원 미만일 경우 최대 7만3천원 혜택 한도
        </p>
        """

        parsed = ShinhanAdapter().parse_product(
            "https://www.shinhancard.com/pconts/html/card/apply/credit/"
            "123_2207.html",
            html,
        )

        self.assertEqual(
            [
                (
                    tier["minimum_spending"],
                    tier["maximum_spending"],
                    tier["monthly_discount_limit"],
                )
                for tier in parsed["benefit_tiers"]
            ],
            [
                (400000, 800000, 30000),
                (800000, 1200000, 50000),
                (1200000, 1500000, 70000),
                (1500000, 1800000, 73000),
                (1800000, None, 100000),
            ],
        )

    def test_deep_oil_parser_splits_life_benefits_and_shared_limits(self):
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "name": "신한카드 Deep Oil"}
        </script>
        <h4>생활서비스 5% 할인</h4>
        <ul>
          <li>편의점 GS25, CU 5% 결제일 할인</li>
          <li>커피 스타벅스, 이디야 5% 결제일 할인</li>
        </ul>
        <table>
          <tr>
            <td>전월 이용 금액</td>
            <td>30만원 이상 70만원 미만</td>
            <td>15만원</td><td>15만원</td><td>15만원</td><td>1회</td>
          </tr>
          <tr>
            <td>70만원 이상</td>
            <td>30만원</td><td>30만원</td><td>30만원</td><td>2회</td>
          </tr>
        </table>
        """
        parsed = ShinhanAdapter().parse_product(
            "https://www.shinhancard.com/pconts/html/card/apply/credit/"
            "1188274_2207.html",
            html,
        )

        life_benefits = [
            benefit
            for benefit in parsed["benefits"]
            if benefit.get("benefit_group") == "life_service"
        ]
        self.assertEqual(
            {benefit["category"] for benefit in life_benefits},
            {"cafe", "convenience"},
        )
        self.assertEqual(
            [
                (
                    tier["minimum_spending"],
                    tier["maximum_spending"],
                    tier["monthly_spending_limit"],
                    tier["monthly_discount_limit"],
                )
                for tier in parsed["service_limit_tiers"]
            ],
            [
                (300000, 700000, 150000, 7500),
                (700000, None, 300000, 15000),
            ],
        )
