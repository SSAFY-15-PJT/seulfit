from email.message import Message
from io import BytesIO

from django.test import TestCase

from finance.adapters.base import CollectionPolicyBlocked
from finance.adapters.kakaobank import KakaoBankAdapter
from finance.card_ingestion import persist_parsed_card
from finance.models import (
    CardProduct,
    CrawlItem,
    CrawlJob,
    ParseStatus,
)


class FakeResponse(BytesIO):
    def __init__(self, content, content_type="text/html; charset=utf-8"):
        super().__init__(content.encode("utf-8"))
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class KakaoBankAdapterTests(TestCase):
    def test_robots_policy_blocks_generic_crawler(self):
        def opener(_request, timeout):
            self.assertEqual(timeout, 15)
            return FakeResponse("User-agent: *\nDisallow: /\n", "text/plain")

        adapter = KakaoBankAdapter(opener=opener)

        with self.assertRaises(CollectionPolicyBlocked):
            adapter.discover_items()

    def test_discovery_extracts_credit_details_when_policy_allows(self):
        listing = """
        <a href="/products/creditCard/detail?card_gds_code=000200001">KB</a>
        <a href="/products/creditCard/detail?card_gds_code=000300001">Samsung</a>
        """

        def opener(request, timeout):
            if request.full_url.endswith("/robots.txt"):
                return FakeResponse("User-agent: *\nAllow: /\n", "text/plain")
            return FakeResponse(listing)

        items = KakaoBankAdapter(opener=opener).discover_items()

        self.assertEqual(len(items), 4)
        self.assertIn(
            "credit-000200001",
            {item["external_id"] for item in items},
        )

    def test_credit_product_parsing_separates_issuer_and_provider(self):
        html = """
        <meta property="og:title" content="카카오뱅크 삼성카드">
        <meta property="og:image" content="https://images.example/card.png">
        <h1>카카오뱅크 삼성카드</h1>
        <p>편의점 1% 할인</p>
        <p>커피전문점 5% 할인</p>
        <p>연회비 국내전용, VISA, Master 7,000원</p>
        <p>전월 이용금액 50만원 이상</p>
        <p>자주 가는 곳에선 월 최대 2만원 할인</p>
        """
        url = (
            "https://www.kakaobank.com/products/creditCard/detail"
            "?card_gds_code=000300001"
        )

        parsed = KakaoBankAdapter().parse_product(url, html)

        self.assertEqual(parsed["external_id"], "credit-000300001")
        self.assertEqual(parsed["issuer"], "삼성카드")
        self.assertEqual(parsed["provider"], "카카오뱅크")
        self.assertEqual(parsed["annual_fee"], 7000)
        self.assertEqual(parsed["previous_month_requirement"], 500000)
        self.assertEqual(parsed["monthly_discount_limit"], 20000)
        self.assertGreaterEqual(len(parsed["benefits"]), 2)

    def test_parsed_card_is_persisted_idempotently_with_snapshot(self):
        job = CrawlJob.objects.create(source_channel="kakaobank")
        item = CrawlItem.objects.create(
            job=job,
            external_id="checkcard",
            source_url="https://www.kakaobank.com/products/checkcard",
        )
        html = """
        <meta property="og:title" content="카카오뱅크 프렌즈 체크카드">
        <meta property="og:image" content="https://images.example/card.png">
        <h1>카카오뱅크 프렌즈 체크카드</h1>
        <p>평일 0.2% 캐시백</p>
        <p>주말/공휴일 0.4% 캐시백</p>
        <p>랜덤 캐시백 제공</p>
        <p>연회비 없음</p>
        """
        adapter = KakaoBankAdapter()
        parsed = adapter.parse_product(item.source_url, html)

        first_card, first_validation = persist_parsed_card(item, parsed, html)
        second_card, _ = persist_parsed_card(item, parsed, html)

        self.assertEqual(first_card.pk, second_card.pk)
        self.assertEqual(CardProduct.objects.count(), 1)
        self.assertEqual(first_validation.parse_status, ParseStatus.REVIEW_REQUIRED)
        self.assertTrue(
            any("random_reward" in reason for reason in first_card.review_reasons)
        )
        self.assertEqual(first_card.snapshots.count(), 2)
        self.assertEqual(first_card.images.count(), 1)
