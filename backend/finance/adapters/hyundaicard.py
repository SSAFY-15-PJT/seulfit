import re
import ssl
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import HTTPSHandler, build_opener

from django.conf import settings

from .base import BaseCardAdapter, ProductPageParser


CATEGORY_PATTERNS = {
    "cafe": ("카페", "커피"),
    "convenience": ("편의점",),
    "mart": ("마트", "슈퍼"),
    "food": ("음식점", "외식", "배달"),
    "shopping": ("쇼핑", "백화점"),
}


class HyundaiCardAdapter(BaseCardAdapter):
    source_key = "hyundai"
    base_url = "https://www.hyundaicard.com/cpc/cr/CPCCR0201_01.hc"
    robots_url = "https://www.hyundaicard.com/robots.txt"
    product_codes = ("TBE4", "TPE4", "TRSTE2", "TRE6")

    def __init__(self, opener=None):
        if opener is None:
            context = ssl.create_default_context()
            context.options |= ssl.OP_LEGACY_SERVER_CONNECT
            opener = build_opener(HTTPSHandler(context=context)).open
        super().__init__(opener=opener)

    def discover_items(self, limit=None):
        self.assert_collection_allowed()
        items = [
            {
                "external_id": code,
                "source_url": f"{self.base_url}?cardWcd={code}",
            }
            for code in self.product_codes
        ]
        return items[:limit] if limit is not None else items

    def parse_product(self, source_url, html):
        parser = ProductPageParser(source_url)
        parser.feed(html)
        title = parser.meta.get("title") or parser.meta.get("og:title", "")
        name = re.sub(r"\s*-\s*카드\s*-\s*현대카드\s*$", "", title).strip()
        if not name:
            name = f"현대카드 {self.external_id_from_url(source_url)}"
        image_url = parser.meta.get("og:image") or parser.meta.get(
            "twitter:image",
            "",
        )
        benefits = self._benefits(parser.text)
        annual_fee = self._annual_fee(parser.text)
        review_reasons = []
        if annual_fee is None:
            review_reasons.append("연회비 미확인")
        if not benefits:
            review_reasons.append("구조화된 혜택 규칙이 없음")
        return {
            "external_id": self.external_id_from_url(source_url),
            "issuer": "현대카드",
            "provider": "현대카드",
            "source_channel": self.source_key,
            "card_type": "credit",
            "name": name,
            "source_url": source_url,
            "annual_fee": annual_fee,
            "annual_fee_source_url": source_url if annual_fee is not None else "",
            "previous_month_requirement": self._previous_month_requirement(
                parser.text
            ),
            "monthly_discount_limit": None,
            "raw_text": parser.text,
            "benefits": benefits,
            "review_reasons": review_reasons,
            "images": (
                [{"source_url": image_url, "alt_text": f"{name} 카드 이미지"}]
                if image_url
                else []
            ),
        }

    def run(self, job, retry_failed=False, limit=None, stdout=None):
        from finance.card_ingestion import persist_parsed_card
        from finance.crawling import (
            download_image_atomic,
            enqueue_items,
            run_crawl_job,
        )
        from finance.models import CrawlStatus

        enqueue_items(job, self.discover_items(limit=limit))

        def fetch_item(item):
            html = self.request_text(item.source_url)
            parsed = self.parse_product(item.source_url, html)
            card, validation = persist_parsed_card(item, parsed, html)

            for image in card.images.filter(download_status=CrawlStatus.PENDING):
                suffix = Path(urlparse(image.source_url).path).suffix or ".img"
                destination = (
                    settings.MEDIA_ROOT
                    / "cards"
                    / self.source_key
                    / f"{card.external_id}-{image.pk}{suffix}"
                )
                try:
                    result = download_image_atomic(image.source_url, destination)
                    image.local_path = str(
                        destination.relative_to(settings.MEDIA_ROOT)
                    )
                    image.content_type = result["content_type"]
                    image.checksum = result["checksum"]
                    image.download_status = CrawlStatus.SUCCESS
                    image.last_error = ""
                except Exception as error:
                    image.download_status = CrawlStatus.FAILED
                    image.last_error = str(error)
                image.save(
                    update_fields=[
                        "local_path",
                        "content_type",
                        "checksum",
                        "download_status",
                        "last_error",
                        "updated_at",
                    ]
                )

            if stdout:
                stdout.write(
                    f"{card.name}: {validation.parse_status}, "
                    f"혜택 {card.benefits.count()}개"
                )
            return {
                "card_id": card.pk,
                "external_id": card.external_id,
                "parse_status": validation.parse_status,
            }

        return run_crawl_job(
            job,
            fetch_item,
            retry_failed=retry_failed,
        )

    @staticmethod
    def external_id_from_url(url):
        return parse_qs(urlparse(url).query).get("cardWcd", [""])[0]

    @staticmethod
    def _annual_fee(text):
        match = re.search(
            r"연회비[^\d]{0,100}(\d[\d,]*)\s*원",
            text,
        )
        return int(match.group(1).replace(",", "")) if match else None

    @staticmethod
    def _previous_month_requirement(text):
        match = re.search(
            r"전월[^\d]{0,50}(\d+(?:\.\d+)?)\s*(만원|원)\s*이상",
            text,
        )
        if not match:
            return 0
        return int(
            Decimal(match.group(1))
            * (10000 if match.group(2) == "만원" else 1)
        )

    @staticmethod
    def _benefits(text):
        benefits = []
        seen = set()
        for match in re.finditer(
            r"([^.!?]{0,120}?)(\d+(?:\.\d+)?)%\s*(할인|적립|캐시백)",
            text,
        ):
            raw_text = " ".join(match.group(0).split())
            if raw_text in seen:
                continue
            seen.add(raw_text)
            category = next(
                (
                    key
                    for key, keywords in CATEGORY_PATTERNS.items()
                    if any(keyword in raw_text for keyword in keywords)
                ),
                "etc",
            )
            unsupported = ["source_review_required"]
            if category == "etc":
                unsupported.append("category_mapping")
            benefits.append(
                {
                    "category": category,
                    "benefit_group": "",
                    "discount_type": "rate",
                    "discount_rate": str(Decimal(match.group(2)) / 100),
                    "discount_amount": None,
                    "minimum_transaction_amount": 0,
                    "per_transaction_limit": None,
                    "daily_usage_limit": None,
                    "monthly_usage_limit": None,
                    "estimated_monthly_uses": None,
                    "category_monthly_limit": None,
                    "merchant_scope": [],
                    "channel": "all",
                    "condition_text": raw_text,
                    "exclusion_text": "",
                    "raw_text": raw_text,
                    "unsupported_conditions": unsupported,
                }
            )
        return benefits[:20]
