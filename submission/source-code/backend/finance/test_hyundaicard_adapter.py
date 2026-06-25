from email.message import Message
from io import BytesIO

from django.test import SimpleTestCase

from finance.adapters.hyundaicard import HyundaiCardAdapter


class FakeResponse(BytesIO):
    def __init__(self, content, content_type="text/html; charset=utf-8"):
        super().__init__(content.encode("utf-8"))
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class HyundaiCardAdapterTests(SimpleTestCase):
    def test_discovery_uses_four_official_product_codes(self):
        def opener(request, timeout):
            return FakeResponse(
                "User-agent: SeulPickCardCrawler/1.0\nAllow: /cpc/cr/\n",
                "text/plain",
            )

        items = HyundaiCardAdapter(opener=opener).discover_items()

        self.assertEqual(len(items), 4)
        self.assertEqual(items[0]["external_id"], "TBE4")
        self.assertIn("cardWcd=TRE6", items[-1]["source_url"])

    def test_parser_extracts_title_image_fee_and_review_benefit(self):
        html = """
        <meta name="title" content="the Purple - 카드 - 현대카드">
        <meta property="og:image" content="https://example.com/card.png">
        <div>연회비 800,000원 전월 이용실적 50만원 이상 쇼핑 10% 적립</div>
        """

        parsed = HyundaiCardAdapter().parse_product(
            "https://www.hyundaicard.com/cpc/cr/CPCCR0201_01.hc"
            "?cardWcd=TPE4",
            html,
        )

        self.assertEqual(parsed["name"], "the Purple")
        self.assertEqual(parsed["annual_fee"], 800000)
        self.assertEqual(parsed["previous_month_requirement"], 500000)
        self.assertEqual(parsed["benefits"][0]["category"], "shopping")
        self.assertIn(
            "source_review_required",
            parsed["benefits"][0]["unsupported_conditions"],
        )
