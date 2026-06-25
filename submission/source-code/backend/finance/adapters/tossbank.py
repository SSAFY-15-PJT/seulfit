import re
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings

from .base import BaseCardAdapter, ProductPageParser


CATEGORY_PATTERNS = {
    "cafe": ("카페", "커피"),
    "convenience": ("편의점",),
    "mart": ("마트", "슈퍼"),
    "food": ("음식점", "배달"),
    "shopping": ("쇼핑",),
}


class TossBankAdapter(BaseCardAdapter):
    source_key = "tossbank"
    base_url = "https://www.tossbank.com/product-service/card/"
    robots_url = "https://www.tossbank.com/robots.txt"
    product_slugs = (
        "check-card",
        "day-card",
        "individual-business-card",
        "moim-card",
        "wide-card",
    )
    product_names = {
        "check-card": "토스뱅크 체크카드",
        "day-card": "토스뱅크 데이카드",
        "individual-business-card": "토스뱅크 개인사업자 체크카드",
        "moim-card": "토스뱅크 모임카드",
        "wide-card": "토스뱅크 와이드카드",
    }

    def discover_items(self, limit=None):
        self.assert_collection_allowed()
        items = [
            {
                "external_id": slug,
                "source_url": f"{self.base_url}{slug}",
            }
            for slug in self.product_slugs
        ]
        return items[:limit] if limit is not None else items

    def parse_product(self, source_url, html):
        parser = ProductPageParser(source_url)
        parser.feed(html)
        slug = self.external_id_from_url(source_url)
        is_credit = slug in {"day-card", "wide-card"}
        name = (
            parser.meta.get("og:title")
            or parser.meta.get("twitter:title")
            or self.product_names.get(slug, "토스뱅크 카드")
        )
        name = re.sub(r"\s*\|\s*토스뱅크.*$", "", name).strip()
        if name in {"", "토스뱅크"}:
            name = self.product_names.get(slug, "토스뱅크 카드")
        image_url = parser.meta.get("og:image") or parser.meta.get(
            "twitter:image",
            "",
        )
        benefits = self._specialized_benefits(slug)
        if benefits is None:
            benefits = self._benefits(parser.text)
        benefit_tiers = self._specialized_benefit_tiers(slug)
        service_limit_tiers = self._specialized_service_limit_tiers(slug)
        review_reasons = (
            ["구조화된 혜택 규칙이 없음"] if not benefits else []
        )
        previous_month_requirement = self._previous_month_requirement(
            parser.text
        )
        if slug in {"individual-business-card", "wide-card"}:
            previous_month_requirement = 0

        return {
            "external_id": slug,
            "issuer": "하나카드" if is_credit else "토스뱅크",
            "provider": "토스뱅크",
            "source_channel": self.source_key,
            "card_type": "credit" if is_credit else "debit",
            "name": name,
            "source_url": source_url,
            "annual_fee": 20000 if is_credit else 0,
            "annual_fee_source_url": source_url,
            "previous_month_requirement": previous_month_requirement,
            "monthly_discount_limit": 100000 if slug == "wide-card" else None,
            "raw_text": parser.text,
            "benefits": benefits,
            "benefit_tiers": benefit_tiers,
            "service_limit_tiers": service_limit_tiers,
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
        return urlparse(url).path.rstrip("/").split("/")[-1]

    @staticmethod
    def _previous_month_requirement(text):
        match = re.search(
            r"전월[^\d]{0,40}(\d+(?:\.\d+)?)\s*(만원|원)\s*이상",
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
            r"([^.!?]{0,100}?)(\d+(?:\.\d+)?)%\s*(캐시백|할인|적립)",
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

    @staticmethod
    def _specialized_benefits(slug):
        rates = {
            "individual-business-card": (
                "0.003",
                None,
                "국내 모든 가맹점 결제금액 0.3% 캐시백",
            ),
            "wide-card": (
                "0.01",
                100000,
                "국내외 가맹점 최소 1% 청구할인, 월 최대 10만원",
            ),
        }
        if slug not in rates:
            if slug == "day-card":
                return [
                    {
                        "category": "cafe",
                        "benefit_group": "day_cafe",
                        "discount_type": "rate",
                        "discount_rate": "0.10",
                        "discount_amount": None,
                        "minimum_transaction_amount": 0,
                        "maximum_transaction_amount": None,
                        "per_transaction_limit": None,
                        "daily_benefit_limit": None,
                        "daily_usage_limit": None,
                        "monthly_usage_limit": None,
                        "estimated_monthly_uses": None,
                        "category_monthly_limit": None,
                        "merchant_scope": [
                            "스타벅스",
                            "커피빈",
                            "이디야",
                            "투썸플레이스",
                            "할리스",
                        ],
                        "channel": "offline",
                        "start_hour": None,
                        "end_hour": None,
                        "condition_text": "국내 커피 대상점",
                        "exclusion_text": "",
                        "raw_text": "국내 커피 대상점 10% 청구할인",
                        "unsupported_conditions": [],
                    },
                    {
                        "category": "mart",
                        "benefit_group": "day_shopping",
                        "discount_type": "rate",
                        "discount_rate": "0.10",
                        "discount_amount": None,
                        "minimum_transaction_amount": 0,
                        "maximum_transaction_amount": None,
                        "per_transaction_limit": None,
                        "daily_benefit_limit": None,
                        "daily_usage_limit": None,
                        "monthly_usage_limit": None,
                        "estimated_monthly_uses": None,
                        "category_monthly_limit": None,
                        "merchant_scope": ["이마트", "롯데마트", "홈플러스"],
                        "channel": "offline",
                        "start_hour": None,
                        "end_hour": None,
                        "condition_text": "대형마트 오프라인 결제",
                        "exclusion_text": "",
                        "raw_text": "이마트·롯데마트·홈플러스 10% 청구할인",
                        "unsupported_conditions": [],
                    },
                    {
                        "category": "shopping",
                        "benefit_group": "day_shopping",
                        "discount_type": "rate",
                        "discount_rate": "0.10",
                        "discount_amount": None,
                        "minimum_transaction_amount": 0,
                        "maximum_transaction_amount": None,
                        "per_transaction_limit": None,
                        "daily_benefit_limit": None,
                        "daily_usage_limit": None,
                        "monthly_usage_limit": None,
                        "estimated_monthly_uses": None,
                        "category_monthly_limit": None,
                        "merchant_scope": ["토스쇼핑"],
                        "channel": "online",
                        "start_hour": None,
                        "end_hour": None,
                        "condition_text": "토스쇼핑 공식 앱",
                        "exclusion_text": "",
                        "raw_text": "토스쇼핑 공식 앱 10% 청구할인",
                        "unsupported_conditions": [],
                    },
                ]
            if slug == "moim-card":
                return [
                    {
                        "category": "mart",
                        "benefit_group": "moim_mart",
                        "discount_type": "amount",
                        "discount_rate": None,
                        "discount_amount": 500,
                        "minimum_transaction_amount": 10000,
                        "maximum_transaction_amount": None,
                        "per_transaction_limit": None,
                        "daily_benefit_limit": None,
                        "daily_usage_limit": 1,
                        "monthly_usage_limit": 5,
                        "estimated_monthly_uses": None,
                        "category_monthly_limit": 2500,
                        "merchant_scope": [
                            "이마트",
                            "이마트 트레이더스",
                            "농협하나로마트",
                            "농협하나로클럽",
                        ],
                        "channel": "offline",
                        "start_hour": None,
                        "end_hour": None,
                        "condition_text": "마트 당일 첫 결제 건",
                        "exclusion_text": "",
                        "raw_text": (
                            "마트 1만원 이상 결제 시 500원 캐시백, "
                            "일 1회·월 5회"
                        ),
                        "unsupported_conditions": [],
                    },
                    {
                        "category": "food",
                        "benefit_group": "moim_food",
                        "discount_type": "amount",
                        "discount_rate": None,
                        "discount_amount": 500,
                        "minimum_transaction_amount": 10000,
                        "maximum_transaction_amount": None,
                        "per_transaction_limit": None,
                        "daily_benefit_limit": None,
                        "daily_usage_limit": 1,
                        "monthly_usage_limit": 5,
                        "estimated_monthly_uses": None,
                        "category_monthly_limit": 2500,
                        "merchant_scope": [],
                        "channel": "offline",
                        "start_hour": 19,
                        "end_hour": 24,
                        "condition_text": "음식점·주점 19시 이상 24시 미만",
                        "exclusion_text": "",
                        "raw_text": (
                            "저녁 음식점·주점 1만원 이상 결제 시 500원 "
                            "캐시백, 일 1회·월 5회"
                        ),
                        "unsupported_conditions": [],
                    },
                ]
            return None
        rate, category_limit, raw_text = rates[slug]
        return [
            {
                "category": category,
                "benefit_group": "",
                "discount_type": "rate",
                "discount_rate": rate,
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
                "unsupported_conditions": [],
            }
            for category in (
                "cafe",
                "convenience",
                "mart",
                "food",
                "shopping",
                "etc",
            )
        ]

    @staticmethod
    def _specialized_benefit_tiers(slug):
        if slug != "day-card":
            return []
        return [
            {
                "scope": "card_total",
                "minimum_spending": minimum,
                "maximum_spending": maximum,
                "monthly_discount_limit": limit,
                "raw_text": raw_text,
            }
            for minimum, maximum, limit, raw_text in (
                (500000, 1000000, 30000, "50만원 이상 100만원 미만 통합 3만원"),
                (1000000, None, 50000, "100만원 이상 통합 5만원"),
            )
        ]

    @staticmethod
    def _specialized_service_limit_tiers(slug):
        if slug != "day-card":
            return []
        return [
            {
                "benefit_group": group,
                "minimum_spending": minimum,
                "maximum_spending": maximum,
                "monthly_spending_limit": None,
                "monthly_discount_limit": limit,
                "monthly_usage_limit": None,
                "raw_text": raw_text,
            }
            for group in ("day_cafe", "day_shopping")
            for minimum, maximum, limit, raw_text in (
                (500000, 1000000, 5000, "50만원 이상 100만원 미만 영역별 5천원"),
                (1000000, None, 10000, "100만원 이상 영역별 1만원"),
            )
        ]
