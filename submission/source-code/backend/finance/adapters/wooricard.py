import json
import re
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings

from .base import BaseCardAdapter, ProductPageParser


CATEGORY_PATTERNS = {
    "cafe": ("카페", "커피", "스타벅스"),
    "convenience": ("편의점", "CU", "GS25"),
    "mart": ("마트", "할인점", "슈퍼"),
    "food": ("음식점", "배달", "외식"),
    "shopping": ("쇼핑", "백화점", "온라인몰"),
}


def _strip_tags(value):
    parser = ProductPageParser("https://m.wooricard.com")
    parser.feed(value)
    return parser.text


def _parse_won(value):
    normalized = str(value or "").replace(",", "").replace(" ", "")
    if "없음" in normalized and not re.search(r"\d", normalized):
        return 0
    match = re.search(r"(\d+(?:\.\d+)?)만원", normalized)
    if match:
        return int(Decimal(match.group(1)) * 10000)
    amounts = [int(item) for item in re.findall(r"(\d+)원", normalized)]
    return min(amounts) if amounts else None


class WooriCardAdapter(BaseCardAdapter):
    source_key = "wooricard"
    base_url = "https://m.wooricard.com/ai-data/"
    robots_url = "https://pc.wooricard.com/robots.txt"
    sitemap_url = "https://m.wooricard.com/sitemap.xml"
    default_limit = 15

    def discover_items(self, limit=None):
        self.assert_collection_allowed()
        sitemap = self.request_text(self.sitemap_url)
        urls = re.findall(
            r"<loc>(https://m\.wooricard\.com/ai-data/card_[^<]+)</loc>",
            sitemap,
        )
        effective_limit = limit or self.default_limit
        return [
            {
                "external_id": self.external_id_from_url(url),
                "source_url": url,
            }
            for url in urls[:effective_limit]
        ]

    def parse_product(self, source_url, html):
        parser = ProductPageParser(source_url)
        parser.feed(html)
        payload = self._product_json(html)
        name = payload.get("name") or parser.meta.get("description") or "우리카드"
        annual_fee = _parse_won(payload.get("annualFee"))
        card_type = self._card_type(name, parser.text)
        benefits = self._specialized_benefits(name)
        service_limit_tiers = self._specialized_service_limit_tiers(name)
        if benefits is None:
            benefits = self._benefits(html)
        review_reasons = []
        if annual_fee is None:
            review_reasons.append("연회비 미확인")
        if not benefits:
            review_reasons.append("구조화된 혜택 규칙이 없음")

        image_url = payload.get("image", "")
        previous_month_requirement = self._previous_month_requirement(
            parser.text
        )
        if name in {
            "NU Biz",
            "KREAM 우리카드",
            "DA카드의정석 Ⅱ",
            "카드의정석 I&U+",
            "카드의정석2 EVERY POINT",
        }:
            previous_month_requirement = 0

        return {
            "external_id": self.external_id_from_url(source_url),
            "issuer": "우리카드",
            "provider": "우리카드",
            "source_channel": self.source_key,
            "card_type": card_type,
            "name": name,
            "source_url": source_url,
            "annual_fee": annual_fee,
            "annual_fee_source_url": source_url if annual_fee is not None else "",
            "previous_month_requirement": previous_month_requirement,
            "monthly_discount_limit": None,
            "raw_text": parser.text,
            "benefits": benefits,
            "benefit_tiers": [],
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

        discovered_items = self.discover_items(limit=limit)
        enqueue_items(job, discovered_items)

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
        return Path(urlparse(url).path).stem.replace("card_", "")

    @staticmethod
    def _product_json(html):
        for block in re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>'
            r"([\s\S]*?)</script>",
            html,
            flags=re.IGNORECASE,
        ):
            try:
                payload = json.loads(block)
            except json.JSONDecodeError:
                continue
            if payload.get("@type") == "CreditCard":
                return payload
        return {}

    @staticmethod
    def _previous_month_requirement(text):
        amounts = []
        for value, unit in re.findall(
            r"전월[^\d]{0,40}(\d+(?:\.\d+)?)\s*(만원|원)\s*이상",
            text,
        ):
            amounts.append(
                int(Decimal(value) * (10000 if unit == "만원" else 1))
            )
        return min(amounts, default=0)

    @staticmethod
    def _card_type(name, text):
        if "체크" in name.casefold() or "check" in name.casefold():
            return "debit"
        match = re.search(r"카드 종류\s*(신용카드|체크카드)", text)
        if match:
            return "debit" if match.group(1) == "체크카드" else "credit"
        return "credit"

    @staticmethod
    def _benefits(html):
        benefits = []
        sections = re.findall(
            r"<h3[^>]*>([\s\S]*?)</h3>([\s\S]*?)(?=<h3|</section>|$)",
            html,
            flags=re.IGNORECASE,
        )
        for heading_html, body_html in sections:
            raw_text = _strip_tags(f"{heading_html} {body_html}")
            rate_match = re.search(
                r"(\d+(?:\.\d+)?)%\s*(?:청구)?(?:할인|적립|캐시백)",
                raw_text,
            )
            amount_match = re.search(
                r"(\d[\d,]*)원\s*(?:청구)?(?:할인|적립|캐시백)",
                raw_text,
            )
            if not rate_match and not amount_match:
                continue
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
                    "discount_type": "rate" if rate_match else "amount",
                    "discount_rate": (
                        str(Decimal(rate_match.group(1)) / 100)
                        if rate_match
                        else None
                    ),
                    "discount_amount": (
                        int(amount_match.group(1).replace(",", ""))
                        if amount_match and not rate_match
                        else None
                    ),
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
        return benefits

    @staticmethod
    def _all_category_rate(rate, raw_text):
        return [
            {
                "category": category,
                "benefit_group": "",
                "discount_type": "rate",
                "discount_rate": str(rate),
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

    @classmethod
    def _specialized_benefits(cls, card_name):
        rates = {
            "NU Biz": ("0.005", "국내 가맹점 기본 0.5% 포인트 적립"),
            "KREAM 우리카드": (
                "0.005",
                "국내외 가맹점 기본 0.5% 청구할인",
            ),
            "DA카드의정석 Ⅱ": (
                "0.008",
                "국내외 가맹점 기본 0.8% 청구할인",
            ),
            "카드의정석 I&U+": (
                "0.007",
                "국내 가맹점 기본 0.7% 청구할인",
            ),
            "카드의정석2 EVERY POINT": (
                "0.008",
                "국내외 가맹점 기본 0.8% 적립",
            ),
            "트래블월렛 우리카드": (
                "0.01",
                "전월 40만원 이상 국내 이용금액 1% 적립",
            ),
        }
        if card_name in rates:
            rate, raw_text = rates[card_name]
            return cls._all_category_rate(rate, raw_text)

        partner_cards = {
            "LG전자 우리카드": ("lg_subscription", ["LG전자"]),
            "넥센타이어 우리카드 Ⅱ": ("nexen_rental", ["넥센타이어"]),
        }
        if card_name in partner_cards:
            benefit_group, merchant_scope = partner_cards[card_name]
            return [
                {
                    "category": "shopping",
                    "benefit_group": benefit_group,
                    "discount_type": "amount",
                    "discount_rate": None,
                    "discount_amount": 20000,
                    "minimum_transaction_amount": 0,
                    "per_transaction_limit": None,
                    "daily_usage_limit": None,
                    "monthly_usage_limit": 1,
                    "estimated_monthly_uses": 1,
                    "category_monthly_limit": None,
                    "merchant_scope": merchant_scope,
                    "channel": "all",
                    "condition_text": "제휴 요금 자동납부 또는 장기할부",
                    "exclusion_text": "",
                    "raw_text": (
                        f"{merchant_scope[0]} 제휴 결제 실적별 월 청구할인"
                    ),
                    "unsupported_conditions": [],
                }
            ]
        if card_name == "카드의정석 SHOPPING+":
            offline_scopes = {
                "mart": [
                    "이마트",
                    "홈플러스",
                    "롯데마트",
                    "메가마트",
                    "Y_MART",
                    "트레이더스",
                    "롯데마트 맥스",
                    "이케아",
                    "이마트 에브리데이",
                    "롯데슈퍼",
                    "홈플러스 익스프레스",
                    "GS 수퍼마켓",
                ],
                "convenience": ["CU", "GS25", "이마트24"],
                "shopping": [
                    "롯데백화점",
                    "현대백화점",
                    "신세계백화점",
                    "롯데아울렛",
                    "현대아울렛",
                    "신세계아울렛",
                    "올리브영",
                    "LOHB's",
                    "시코르",
                    "다이소",
                ],
            }
            return [
                {
                    "category": category,
                    "benefit_group": "shopping_plus_offline",
                    "discount_type": "rate",
                    "discount_rate": "0.10",
                    "discount_amount": None,
                    "minimum_transaction_amount": 0,
                    "maximum_transaction_amount": None,
                    "per_transaction_limit": 5000,
                    "daily_benefit_limit": None,
                    "daily_usage_limit": None,
                    "monthly_usage_limit": None,
                    "estimated_monthly_uses": None,
                    "category_monthly_limit": None,
                    "merchant_scope": merchant_scope,
                    "channel": "offline",
                    "condition_text": "오프라인 쇼핑 대상점 10% 청구할인",
                    "exclusion_text": "",
                    "raw_text": (
                        "오프라인 쇼핑 대상점 10% 청구할인, "
                        "매출 건당 5만원까지 적용, 전월 실적별 월 한도"
                    ),
                    "unsupported_conditions": [],
                }
                for category, merchant_scope in offline_scopes.items()
            ]
        if card_name == "카드의정석 오하CHECK":
            services = (
                (
                    "shopping",
                    "oha_shopping",
                    ["쿠팡", "무신사", "지그재그", "네이버페이", "우리WON페이"],
                ),
                (
                    "cafe",
                    "oha_eat",
                    ["스타벅스"],
                ),
                (
                    "food",
                    "oha_eat",
                    ["배달의민족", "쿠팡이츠", "B마트", "마켓컬리"],
                ),
            )
            return [
                {
                    "category": category,
                    "benefit_group": benefit_group,
                    "discount_type": "rate",
                    "discount_rate": "0.05",
                    "discount_amount": None,
                    "minimum_transaction_amount": 0,
                    "maximum_transaction_amount": None,
                    "per_transaction_limit": 1000,
                    "daily_benefit_limit": None,
                    "daily_usage_limit": None,
                    "monthly_usage_limit": None,
                    "estimated_monthly_uses": None,
                    "category_monthly_limit": None,
                    "merchant_scope": merchant_scope,
                    "channel": "online",
                    "condition_text": "공식 앱·웹 대상 가맹점 5% 캐시백",
                    "exclusion_text": "",
                    "raw_text": (
                        "SHOPPING·EAT 공식 대상 가맹점 5% 캐시백, "
                        "매출 건당 최대 1천원, 전월 실적별 그룹 한도"
                    ),
                    "unsupported_conditions": [],
                }
                for category, benefit_group, merchant_scope in services
            ]
        if card_name == "카드의정석2 칼퇴 CHECK":
            services = (
                ("food", [], 30000, 3000, 3),
                (
                    "cafe",
                    [
                        "스타벅스",
                        "투썸플레이스",
                        "폴바셋",
                        "메가MGC커피",
                        "컴포즈커피",
                    ],
                    10000,
                    2000,
                    3,
                ),
                ("convenience", ["CU"], 10000, 2000, 2),
            )
            return [
                {
                    "category": category,
                    "benefit_group": "kaltoe_evening",
                    "discount_type": "rate",
                    "discount_rate": "0.05",
                    "discount_amount": None,
                    "minimum_transaction_amount": minimum_amount,
                    "maximum_transaction_amount": None,
                    "per_transaction_limit": transaction_limit,
                    "daily_benefit_limit": None,
                    "daily_usage_limit": 1,
                    "monthly_usage_limit": monthly_usage_limit,
                    "estimated_monthly_uses": None,
                    "category_monthly_limit": None,
                    "merchant_scope": merchant_scope,
                    "channel": "offline",
                    "start_hour": 18,
                    "end_hour": 23,
                    "condition_text": "저녁 6시 이상 11시 미만 결제 건",
                    "exclusion_text": "",
                    "raw_text": (
                        "음식점·카페·편의점 저녁 6시 이상 11시 미만 "
                        "5% 캐시백, 일 1회 및 월 횟수·거래당 한도 적용"
                    ),
                    "unsupported_conditions": [],
                }
                for (
                    category,
                    merchant_scope,
                    minimum_amount,
                    transaction_limit,
                    monthly_usage_limit,
                ) in services
            ]
        if card_name in {"국민행복카드S2", "국민행복 체크카드S2"}:
            is_debit = "체크" in card_name
            rate = "0.02" if is_debit else "0.05"
            per_transaction_limit = 10000 if is_debit else 2500
            services = (
                (
                    "mart",
                    "offline",
                    [
                        "이마트",
                        "롯데마트",
                        "트레이더스",
                        "롯데VIC마켓",
                    ],
                ),
                (
                    "shopping",
                    "offline",
                    [
                        "롯데백화점",
                        "신세계백화점",
                        "현대백화점",
                        "갤러리아백화점",
                    ],
                ),
                (
                    "shopping",
                    "online",
                    [
                        "쿠팡",
                        "11번가",
                        "위메프",
                        "G마켓",
                        "옥션",
                        "인터파크",
                        "롯데ON",
                    ],
                ),
            )
            return [
                {
                    "category": category,
                    "benefit_group": "happy_shopping_life",
                    "discount_type": "rate",
                    "discount_rate": rate,
                    "discount_amount": None,
                    "minimum_transaction_amount": 0,
                    "maximum_transaction_amount": None,
                    "per_transaction_limit": per_transaction_limit,
                    "daily_benefit_limit": None,
                    "daily_usage_limit": None,
                    "monthly_usage_limit": None,
                    "estimated_monthly_uses": None,
                    "category_monthly_limit": None,
                    "merchant_scope": merchant_scope,
                    "channel": channel,
                    "start_hour": None,
                    "end_hour": None,
                    "condition_text": "쇼핑·생활 공식 대상 가맹점",
                    "exclusion_text": "",
                    "raw_text": (
                        f"쇼핑·생활 대상 가맹점 {Decimal(rate) * 100}% 혜택, "
                        "거래당 대상 금액 및 전월 실적별 그룹 한도 적용"
                    ),
                    "unsupported_conditions": [],
                }
                for category, channel, merchant_scope in services
            ]
        if card_name == "GS칼텍스 화물복지카드":
            return [
                {
                    "category": "mart",
                    "benefit_group": "gs_freight_mart",
                    "discount_type": "rate",
                    "discount_rate": "0.05",
                    "discount_amount": None,
                    "minimum_transaction_amount": 0,
                    "maximum_transaction_amount": None,
                    "per_transaction_limit": None,
                    "daily_benefit_limit": None,
                    "daily_usage_limit": 1,
                    "monthly_usage_limit": 3,
                    "estimated_monthly_uses": None,
                    "category_monthly_limit": None,
                    "merchant_scope": ["이마트", "롯데마트", "홈플러스"],
                    "channel": "offline",
                    "start_hour": None,
                    "end_hour": None,
                    "condition_text": "대형마트 오프라인 5% 청구할인",
                    "exclusion_text": "",
                    "raw_text": (
                        "대형마트 5% 청구할인, 통합 일 1회·월 3회, "
                        "전월 실적별 월 한도"
                    ),
                    "unsupported_conditions": [],
                },
                {
                    "category": "cafe",
                    "benefit_group": "gs_freight_cafe",
                    "discount_type": "rate",
                    "discount_rate": "0.25",
                    "discount_amount": None,
                    "minimum_transaction_amount": 0,
                    "maximum_transaction_amount": None,
                    "per_transaction_limit": None,
                    "daily_benefit_limit": None,
                    "daily_usage_limit": 1,
                    "monthly_usage_limit": 2,
                    "estimated_monthly_uses": None,
                    "category_monthly_limit": None,
                    "merchant_scope": ["스타벅스", "커피빈", "투썸플레이스"],
                    "channel": "offline",
                    "start_hour": None,
                    "end_hour": None,
                    "condition_text": "커피전문점 25% 청구할인",
                    "exclusion_text": "",
                    "raw_text": (
                        "커피전문점 25% 청구할인, 통합 일 1회·월 2회, "
                        "월 최대 5천원"
                    ),
                    "unsupported_conditions": [],
                },
            ]
        return None

    @staticmethod
    def _specialized_service_limit_tiers(card_name):
        groups = {
            "LG전자 우리카드": "lg_subscription",
            "넥센타이어 우리카드 Ⅱ": "nexen_rental",
        }
        benefit_group = groups.get(card_name)
        if not benefit_group:
            if card_name == "카드의정석 SHOPPING+":
                return [
                    {
                        "benefit_group": "shopping_plus_offline",
                        "minimum_spending": minimum,
                        "maximum_spending": maximum,
                        "monthly_spending_limit": None,
                        "monthly_discount_limit": limit,
                        "monthly_usage_limit": None,
                        "raw_text": raw_text,
                    }
                    for minimum, maximum, limit, raw_text in (
                        (300000, 700000, 6000, "30만원 이상 70만원 미만 6천원"),
                        (700000, 1200000, 12000, "70만원 이상 120만원 미만 1만2천원"),
                        (1200000, None, 24000, "120만원 이상 2만4천원"),
                    )
                ]
            if card_name == "카드의정석 오하CHECK":
                return [
                    {
                        "benefit_group": benefit_group,
                        "minimum_spending": minimum,
                        "maximum_spending": maximum,
                        "monthly_spending_limit": None,
                        "monthly_discount_limit": limit,
                        "monthly_usage_limit": None,
                        "raw_text": raw_text,
                    }
                    for benefit_group in ("oha_shopping", "oha_eat")
                    for minimum, maximum, limit, raw_text in (
                        (200000, 500000, 2000, "20만원 이상 50만원 미만 2천원"),
                        (500000, 700000, 4000, "50만원 이상 70만원 미만 4천원"),
                        (700000, None, 6000, "70만원 이상 6천원"),
                    )
                ]
            if card_name == "카드의정석2 칼퇴 CHECK":
                return [
                    {
                        "benefit_group": "kaltoe_evening",
                        "minimum_spending": minimum,
                        "maximum_spending": maximum,
                        "monthly_spending_limit": None,
                        "monthly_discount_limit": limit,
                        "monthly_usage_limit": None,
                        "raw_text": raw_text,
                    }
                    for minimum, maximum, limit, raw_text in (
                        (300000, 600000, 4000, "30만원 이상 60만원 미만 4천원"),
                        (600000, 1200000, 8000, "60만원 이상 120만원 미만 8천원"),
                        (1200000, None, 15000, "120만원 이상 1만5천원"),
                    )
                ]
            if card_name in {"국민행복카드S2", "국민행복 체크카드S2"}:
                return [
                    {
                        "benefit_group": "happy_shopping_life",
                        "minimum_spending": minimum,
                        "maximum_spending": maximum,
                        "monthly_spending_limit": None,
                        "monthly_discount_limit": limit,
                        "monthly_usage_limit": None,
                        "raw_text": raw_text,
                    }
                    for minimum, maximum, limit, raw_text in (
                        (300000, 600000, 4000, "30만원 이상 60만원 미만 4천원"),
                        (600000, 900000, 8000, "60만원 이상 90만원 미만 8천원"),
                        (900000, None, 16000, "90만원 이상 1만6천원"),
                    )
                ]
            if card_name == "GS칼텍스 화물복지카드":
                return [
                    {
                        "benefit_group": "gs_freight_mart",
                        "minimum_spending": minimum,
                        "maximum_spending": maximum,
                        "monthly_spending_limit": None,
                        "monthly_discount_limit": limit,
                        "monthly_usage_limit": 3,
                        "raw_text": raw_text,
                    }
                    for minimum, maximum, limit, raw_text in (
                        (300000, 1000000, 5000, "30만원 이상 100만원 미만 5천원"),
                        (1000000, None, 10000, "100만원 이상 1만원"),
                    )
                ] + [
                    {
                        "benefit_group": "gs_freight_cafe",
                        "minimum_spending": 300000,
                        "maximum_spending": None,
                        "monthly_spending_limit": None,
                        "monthly_discount_limit": 5000,
                        "monthly_usage_limit": 2,
                        "raw_text": "전월 30만원 이상 커피 월 최대 5천원",
                    }
                ]
            return []
        return [
            {
                "benefit_group": benefit_group,
                "minimum_spending": minimum,
                "maximum_spending": maximum,
                "monthly_spending_limit": None,
                "monthly_discount_limit": limit,
                "monthly_usage_limit": 1,
                "raw_text": raw_text,
            }
            for minimum, maximum, limit, raw_text in (
                (300000, 700000, 10000, "30만원 이상 70만원 미만 1만원"),
                (700000, 1200000, 15000, "70만원 이상 120만원 미만 1만5천원"),
                (1200000, None, 20000, "120만원 이상 2만원"),
            )
        ]
