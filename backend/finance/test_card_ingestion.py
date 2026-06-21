from django.test import TestCase
from django.utils import timezone

from finance.card_ingestion import persist_parsed_card
from finance.models import (
    CardImage,
    CardProduct,
    CardType,
    CrawlItem,
    CrawlJob,
    CrawlStatus,
    ParseStatus,
)


class CardIngestionTests(TestCase):
    def test_explicit_inactive_override_is_preserved(self):
        source_url = "https://example.com/old-design"
        job = CrawlJob.objects.create(source_channel="test")
        item = CrawlItem.objects.create(job=job, source_url=source_url)
        parsed = {
            "external_id": "old-design",
            "issuer": "카드사",
            "provider": "카드사",
            "source_channel": "test",
            "card_type": CardType.CREDIT,
            "name": "동일 혜택 구형 디자인",
            "source_url": source_url,
            "annual_fee": 0,
            "annual_fee_source_url": source_url,
            "previous_month_requirement": 0,
            "monthly_discount_limit": None,
            "raw_text": "원문",
            "parse_status_override": ParseStatus.INACTIVE,
            "benefits": [
                {
                    "category": "cafe",
                    "discount_type": "rate",
                    "discount_rate": "0.01",
                    "minimum_transaction_amount": 0,
                    "raw_text": "카페 1% 적립",
                }
            ],
        }

        card, validation = persist_parsed_card(item, parsed, "<html></html>")

        self.assertEqual(validation.parse_status, ParseStatus.INACTIVE)
        self.assertEqual(card.parse_status, ParseStatus.INACTIVE)

    def test_recrawl_preserves_successful_image_download(self):
        source_url = "https://example.com/card"
        image_url = "https://example.com/card.webp"
        card = CardProduct.objects.create(
            external_id="card",
            issuer="카드사",
            provider="카드사",
            source_channel="test",
            card_type=CardType.CREDIT,
            name="테스트 카드",
            source_url=source_url,
            annual_fee=0,
            previous_month_requirement=0,
            parse_status=ParseStatus.ACTIVE,
            raw_text="기존 원문",
        )
        image = CardImage.objects.create(
            card=card,
            source_url=image_url,
            local_path="cards/test/card.webp",
            download_status=CrawlStatus.SUCCESS,
        )
        job = CrawlJob.objects.create(source_channel="test")
        item = CrawlItem.objects.create(job=job, source_url=source_url)
        parsed = {
            "external_id": "card",
            "issuer": "카드사",
            "provider": "카드사",
            "source_channel": "test",
            "card_type": CardType.CREDIT,
            "name": "테스트 카드",
            "source_url": source_url,
            "annual_fee": 0,
            "annual_fee_source_url": source_url,
            "previous_month_requirement": 0,
            "monthly_discount_limit": None,
            "raw_text": "새 원문",
            "benefits": [
                {
                    "category": "cafe",
                    "discount_type": "rate",
                    "discount_rate": "0.01",
                    "minimum_transaction_amount": 0,
                    "raw_text": "카페 1% 적립",
                }
            ],
            "images": [{"source_url": image_url, "alt_text": "새 이미지 설명"}],
        }

        persist_parsed_card(item, parsed, "<html>new</html>")

        image.refresh_from_db()
        self.assertEqual(image.download_status, CrawlStatus.SUCCESS)
        self.assertEqual(image.local_path, "cards/test/card.webp")
        self.assertEqual(image.alt_text, "새 이미지 설명")

    def test_recrawl_preserves_verified_annual_fee_and_active_status(self):
        source_url = "https://example.com/deep-oil"
        verified_source_url = "https://example.com/official-card-api"
        card = CardProduct.objects.create(
            external_id="deep-oil",
            issuer="신한카드",
            provider="신한카드",
            source_channel="shinhan",
            card_type=CardType.CREDIT,
            name="신한카드 Deep Oil",
            source_url=source_url,
            annual_fee=10000,
            annual_fee_source_url=verified_source_url,
            annual_fee_verified_at=timezone.now(),
            previous_month_requirement=300000,
            parse_status=ParseStatus.ACTIVE,
            raw_text="기존 원문",
        )
        job = CrawlJob.objects.create(source_channel="shinhan")
        item = CrawlItem.objects.create(job=job, source_url=source_url)
        parsed = {
            "external_id": "deep-oil",
            "issuer": "신한카드",
            "provider": "신한카드",
            "source_channel": "shinhan",
            "card_type": CardType.CREDIT,
            "name": "신한카드 Deep Oil",
            "source_url": source_url,
            "annual_fee": None,
            "previous_month_requirement": 300000,
            "monthly_discount_limit": None,
            "raw_text": "새 원문",
            "review_reasons": ["연회비는 정적 HTML에서 확인할 수 없음"],
            "benefits": [
                {
                    "category": "cafe",
                    "discount_type": "rate",
                    "discount_rate": "0.05",
                    "discount_amount": None,
                    "minimum_transaction_amount": 0,
                    "merchant_scope": ["스타벅스"],
                    "raw_text": "스타벅스 5% 할인",
                }
            ],
        }

        persist_parsed_card(item, parsed, "<html>new</html>")

        card.refresh_from_db()
        self.assertEqual(card.annual_fee, 10000)
        self.assertEqual(card.annual_fee_source_url, verified_source_url)
        self.assertIsNotNone(card.annual_fee_verified_at)
        self.assertEqual(card.parse_status, ParseStatus.ACTIVE)
        self.assertNotIn(
            "연회비는 정적 HTML에서 확인할 수 없음",
            card.review_reasons,
        )
