import re
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from django.conf import settings

from .base import BaseCardAdapter, ParsedImage, ProductPageParser


ISSUER_NAMES = (
    "KB국민카드",
    "삼성카드",
    "롯데카드",
    "신한카드",
    "우리카드",
    "BC카드",
    "현대카드",
    "NH농협카드",
    "IBK기업은행",
)

CATEGORY_PATTERNS = {
    "cafe": ("커피", "카페"),
    "convenience": ("편의점", "CU", "GS25"),
    "mart": ("마트", "슈퍼마켓"),
    "food": ("배달", "음식", "패스트푸드"),
    "shopping": ("쇼핑", "아울렛"),
}


def _parse_won_amount(value):
    value = value.replace(",", "").replace(" ", "")
    if "만" in value:
        return int(Decimal(value.replace("만원", "").replace("만", "")) * 10000)
    return int(re.sub(r"\D", "", value) or 0)


def _unique_images(images):
    seen = set()
    result = []
    for image in images:
        if image.source_url in seen:
            continue
        seen.add(image.source_url)
        result.append(image)
    return result


class KakaoBankAdapter(BaseCardAdapter):
    source_key = "kakaobank"
    base_url = "https://www.kakaobank.com/products/"
    robots_url = "https://www.kakaobank.com/robots.txt"
    check_card_urls = (
        "https://www.kakaobank.com/products/checkcard",
        "https://www.kakaobank.com/products/moimcheckcard",
    )
    credit_list_url = "https://www.kakaobank.com/products/cardplatform"

    def run(self, job, retry_failed=False, limit=None, stdout=None):
        from finance.card_ingestion import persist_parsed_card
        from finance.crawling import (
            download_image_atomic,
            enqueue_items,
            run_crawl_job,
        )
        from finance.models import CrawlStatus

        items = self.discover_items()
        if limit is not None:
            items = items[:limit]
        enqueue_items(job, items)

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

    def discover_items(self):
        self.assert_collection_allowed()
        parser = ProductPageParser(self.credit_list_url)
        parser.feed(self.request_text(self.credit_list_url))
        credit_urls = sorted(
            {
                url
                for url in parser.links
                if "/products/creditCard/detail" in url
            }
        )
        return [
            {"external_id": self.external_id_from_url(url), "source_url": url}
            for url in (*self.check_card_urls, *credit_urls)
        ]

    def parse_product(self, source_url, html):
        parser = ProductPageParser(source_url)
        parser.feed(html)
        text = parser.text
        card_type = "credit" if "/creditCard/detail" in source_url else "debit"
        name = parser.meta.get("og:title") or self._name_from_text(text, card_type)
        issuer = self._issuer_from_text(text, card_type)
        annual_fee = self._annual_fee(text)
        previous_month_requirement = self._previous_month_requirement(text)
        monthly_discount_limit = self._monthly_discount_limit(text)
        benefits, review_reasons = self._benefits(text, card_type)

        images = _unique_images(
            [
                image
                for image in parser.images
                if image.alt_text and "카드" in image.alt_text
            ]
        )
        og_image = parser.meta.get("og:image")
        if og_image:
            images.insert(0, ParsedImage(og_image, "대표 카드 이미지"))
            images = _unique_images(images)

        return {
            "external_id": self.external_id_from_url(source_url),
            "issuer": issuer,
            "provider": "카카오뱅크",
            "source_channel": self.source_key,
            "card_type": card_type,
            "name": name,
            "source_url": source_url,
            "annual_fee": annual_fee,
            "previous_month_requirement": previous_month_requirement,
            "monthly_discount_limit": monthly_discount_limit,
            "raw_text": text,
            "benefits": benefits,
            "review_reasons": review_reasons,
            "images": [
                {"source_url": image.source_url, "alt_text": image.alt_text}
                for image in images[:10]
            ],
        }

    @staticmethod
    def external_id_from_url(url):
        parsed = urlparse(url)
        code = parse_qs(parsed.query).get("card_gds_code", [None])[0]
        return f"credit-{code}" if code else parsed.path.rstrip("/").split("/")[-1]

    @staticmethod
    def _name_from_text(text, card_type):
        if card_type == "debit":
            match = re.search(r"카카오뱅크\s+([가-힣A-Za-z ]+체크카드)", text)
        else:
            match = re.search(r"(카카오뱅크\s+[가-힣A-Za-z0-9 ]+카드)", text)
        return match.group(1).strip() if match else "카카오뱅크 카드"

    @staticmethod
    def _issuer_from_text(text, card_type):
        if card_type == "debit":
            return "카카오뱅크"
        return next((issuer for issuer in ISSUER_NAMES if issuer in text), "확인 필요")

    @staticmethod
    def _annual_fee(text):
        match = re.search(
            r"연회비[^\d]{0,80}"
            r"(\d[\d,]*(?:\.\d+)?\s*만원|\d[\d,]*\s*원)",
            text,
        )
        return _parse_won_amount(match.group(1)) if match else 0

    @staticmethod
    def _previous_month_requirement(text):
        patterns = (
            r"전월실적\s*(\d[\d,]*(?:\.\d+)?\s*만원|\d[\d,]*\s*원)",
            r"전월 이용(?:실적|금액)[^\d]{0,20}(\d[\d,]*(?:\.\d+)?\s*만원|\d[\d,]*\s*원)",
            r"전월실적이\s*(\d[\d,]*(?:\.\d+)?\s*만원|\d[\d,]*\s*원)",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return _parse_won_amount(match.group(1))
        return 0

    @staticmethod
    def _monthly_discount_limit(text):
        match = re.search(
            r"월 최대\s*(\d[\d,]*(?:\.\d+)?\s*만원|\d[\d,]*\s*원)",
            text,
        )
        return _parse_won_amount(match.group(1)) if match else None

    @staticmethod
    def _benefits(text, card_type):
        benefits = []
        review_reasons = []
        sentences = re.split(r"(?<=원)|(?<=할인)|(?<=캐시백)", text)
        for sentence in sentences:
            rate_match = re.search(r"(\d+(?:\.\d+)?)%\s*(할인|캐시백|적립)", sentence)
            if not rate_match:
                continue
            category = next(
                (
                    key
                    for key, keywords in CATEGORY_PATTERNS.items()
                    if any(keyword in sentence for keyword in keywords)
                ),
                "etc",
            )
            unsupported = []
            if any(word in sentence for word in ("주말", "주중", "평일", "공휴일")):
                unsupported.append("weekday_condition")
            benefits.append(
                {
                    "category": category,
                    "discount_type": "rate",
                    "discount_rate": str(Decimal(rate_match.group(1)) / 100),
                    "discount_amount": None,
                    "minimum_transaction_amount": 0,
                    "per_transaction_limit": None,
                    "daily_usage_limit": None,
                    "monthly_usage_limit": None,
                    "estimated_monthly_uses": None,
                    "category_monthly_limit": None,
                    "merchant_scope": [],
                    "channel": "all",
                    "condition_text": sentence.strip(),
                    "exclusion_text": "",
                    "raw_text": sentence.strip(),
                    "unsupported_conditions": unsupported,
                }
            )

        if "랜덤 캐시백" in text:
            review_reasons.append("random_reward: 랜덤 캐시백은 확정 금액으로 계산할 수 없음")
        if card_type == "credit":
            review_reasons.append("제휴 신용카드는 발급사 상품설명서와 교차 검증 필요")
        return benefits, review_reasons
