import json
import re
from math import ceil
from decimal import Decimal
from html import unescape
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

from django.conf import settings

from .base import BaseCardAdapter, ProductPageParser


CATEGORY_PATTERNS = {
    "cafe": ("커피", "카페"),
    "convenience": ("편의점",),
    "mart": ("마트", "할인점", "슈퍼"),
    "food": ("음식점", "배달앱", "외식"),
    "shopping": ("쇼핑", "백화점", "온라인몰"),
}


def _strip_tags(value):
    parser = ProductPageParser("https://www.shinhancard.com")
    parser.feed(value)
    return parser.text


def _parse_korean_won(value):
    normalized = re.sub(r"\s+", "", value).replace(",", "")
    if normalized in {"-", ""}:
        return 0
    man_match = re.search(r"(\d+)만", normalized)
    thousand_match = re.search(r"(\d+)천", normalized)
    plain_match = re.search(r"(\d+)원", normalized)
    amount = 0
    if man_match:
        amount += int(man_match.group(1)) * 10000
    if thousand_match:
        amount += int(thousand_match.group(1)) * 1000
    if not man_match and not thousand_match and plain_match:
        amount = int(plain_match.group(1))
    return amount


class ShinhanAdapter(BaseCardAdapter):
    source_key = "shinhan"
    base_url = "https://www.shinhancard.com/pconts/html/main.html"
    robots_url = "https://www.shinhancard.com/robots.txt"
    image_base_url = "https://cdn.www.shinhancard.com/pconts"
    search_api_url = (
        "https://shapi.shinhancard.com/card-apply/search/v1.0/"
        "searchPagingCardProductList"
    )
    detail_api_url = (
        "https://shapi.shinhancard.com/card-apply/search/v1.0/"
        "getCardProductsInformation"
    )
    search_page_size = 8
    default_limit = 15

    def discover_items(self, limit=None):
        self.assert_collection_allowed()
        effective_limit = limit or self.default_limit
        try:
            api_items = self._discover_api_items(effective_limit)
            if api_items:
                return api_items
        except (
            json.JSONDecodeError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ):
            pass

        return self._discover_main_items(effective_limit)

    def _discover_api_items(self, limit):
        products = []
        page_count = ceil(limit / self.search_page_size)
        for index in range(1, page_count + 1):
            query = urlencode(
                {
                    "pageSize": self.search_page_size,
                    "index": index,
                    "type": 0,
                }
            )
            payload = json.loads(
                self.request_text(f"{self.search_api_url}?{query}")
            )
            if int(payload.get("status", 0)) != 200:
                raise ValueError("신한카드 검색 API 응답 실패")
            page = payload["payload"]
            for product in page.get("cardInformationList", []):
                relative_url = product.get("cardProductUrl", "")
                if "/card/apply/credit/" not in relative_url:
                    continue
                source_url = urljoin(self.base_url, relative_url)
                products.append(
                    {
                        "external_id": self.external_id_from_url(source_url),
                        "source_url": source_url,
                        "name": product.get("cardProductEntryName", ""),
                        "image_url": urljoin(
                            self.image_base_url,
                            product.get("thumbnailImgUrl", ""),
                        ),
                        "annual_fee": product.get("afeAmountOrigin"),
                        "annual_fee_source_url": (
                            f"{self.detail_api_url}?entryId="
                            f"{product.get('cardProductEntryId', '')}"
                        ),
                    }
                )
                if len(products) >= limit:
                    return products
            if index >= int(page.get("totalPage", index)):
                break
        return products

    def _discover_main_items(self, limit):
        html = self.request_text(self.base_url)
        products = []
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
            if payload.get("@type") != "ItemList":
                continue
            for element in payload.get("itemListElement", []):
                product = element.get("item", {})
                url = product.get("url", "")
                if "/card/apply/credit/" not in url:
                    continue
                products.append(
                    {
                        "external_id": self.external_id_from_url(url),
                        "source_url": url,
                        "name": product.get("name", ""),
                        "image_url": product.get("image", ""),
                    }
                )

        unique = {}
        for product in products:
            unique.setdefault(product["source_url"], product)
        items = list(unique.values())
        return items[:limit]

    def parse_product(self, source_url, html, discovered=None):
        discovered = discovered or {}
        parser = ProductPageParser(source_url)
        parser.feed(html)
        text = parser.text
        product_json = self._product_json(html)
        name = (
            product_json.get("name")
            or parser.meta.get("og:title")
            or discovered.get("name")
            or "신한카드"
        )
        images = self._card_images(html)
        if not images and discovered.get("image_url"):
            images = [discovered["image_url"]]

        benefits = self._benefits(html, name)
        specialized_benefits = self._specialized_benefits(name)
        if specialized_benefits is not None:
            benefits = specialized_benefits
        benefit_tiers = self._benefit_tiers(html)
        service_limit_tiers = self._service_limit_tiers(html, name)
        service_limit_tiers.extend(self._specialized_service_limit_tiers(name))
        previous_month_requirement = self._previous_month_requirement(text)
        if name == "신한카드 Unboxing":
            previous_month_requirement = 400000
        if name == "K-패스 신한카드":
            previous_month_requirement = 300000
        annual_fee = discovered.get("annual_fee")
        review_reasons = []
        if annual_fee in (None, ""):
            review_reasons.append(
                "연회비는 정적 상세 HTML에서 확인할 수 없어 검토 필요"
            )
        if (
            ("통합할인한도" in text or "월 통합 혜택 한도" in text)
            and not benefit_tiers
            and not service_limit_tiers
        ):
            review_reasons.append("전월 실적 구간별 통합 한도는 구조 확장 필요")

        result = {
            "external_id": self.external_id_from_url(source_url),
            "issuer": "신한카드",
            "provider": "신한카드",
            "source_channel": self.source_key,
            "card_type": "credit",
            "name": name,
            "source_url": source_url,
            "annual_fee": annual_fee,
            "annual_fee_source_url": discovered.get(
                "annual_fee_source_url",
                "",
            ),
            "previous_month_requirement": previous_month_requirement,
            "monthly_discount_limit": None,
            "raw_text": text,
            "benefits": benefits,
            "benefit_tiers": benefit_tiers,
            "service_limit_tiers": service_limit_tiers,
            "review_reasons": review_reasons,
            "images": [
                {"source_url": image, "alt_text": f"{name} 카드 이미지"}
                for image in images[:5]
            ],
        }
        if (
            name == "신한카드 처음"
            and result["external_id"] == "1227020_2207"
        ):
            result["parse_status_override"] = "inactive"
            result["review_reasons"].append(
                "동일 혜택 상품의 구형 디자인 변형으로 추천 후보에서 제외"
            )
        return result

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
        discovered_by_url = {
            item["source_url"]: item for item in discovered_items
        }

        def fetch_item(item):
            html = self.request_text(item.source_url)
            parsed = self.parse_product(
                item.source_url,
                html,
                discovered=discovered_by_url.get(item.source_url),
            )
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
        filename = urlparse(url).path.rstrip("/").split("/")[-1]
        return filename.removesuffix(".html")

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
            if payload.get("@type") == "Product":
                return payload
        return {}

    def _card_images(self, html):
        paths = re.findall(
            r'(?:webp|img)\s*:\s*["\']'
            r"(/static/images/card/plate/[^\"']+)",
            html,
        )
        unique = []
        for path in paths:
            url = f"{self.image_base_url}{path}"
            if url not in unique:
                unique.append(url)
        return unique

    @staticmethod
    def _previous_month_requirement(text):
        amounts = []
        for value, unit in re.findall(
            r"전월(?:\s+이용금액|\s+실적)?[^\d]{0,50}"
            r"(\d+(?:\.\d+)?)\s*(만원|원)\s*이상",
            text,
        ):
            amount = int(Decimal(value) * (10000 if unit == "만원" else 1))
            if amount > 0:
                amounts.append(amount)
        return min(amounts, default=0)

    @staticmethod
    def _benefits(html, card_name=""):
        sections = re.findall(
            r"<h4[^>]*>([\s\S]*?)</h4>([\s\S]*?)(?=<h[234]|$)",
            html,
            flags=re.IGNORECASE,
        )
        benefits = []
        for heading_html, body_html in sections:
            heading = _strip_tags(heading_html)
            body = _strip_tags(body_html)
            raw_text = unescape(f"{heading} {body}".strip())
            rate_match = re.search(
                r"(\d+(?:\.\d+)?)%\s*(?:할인|적립|캐시백)",
                raw_text,
            )
            amount_match = re.search(
                r"(\d[\d,]*)원\s*(?:할인|캐시백)",
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
            unsupported = []
            if category == "etc":
                unsupported.append("category_mapping")
            if any(word in raw_text for word in ("시간", "시 00분", "주말", "평일")):
                unsupported.append("weekday_condition")
            if any(word in raw_text for word in ("가맹점", "오프라인", "공식 앱")):
                unsupported.append("merchant_scope")

            discount_type = "rate" if rate_match else "amount"
            benefits.append(
                {
                    "category": category,
                    "discount_type": discount_type,
                    "discount_rate": (
                        str(Decimal(rate_match.group(1)) / 100)
                        if rate_match
                        else None
                    ),
                    "discount_amount": (
                        int(amount_match.group(1).replace(",", ""))
                        if amount_match
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
        if "Deep Oil" in card_name:
            benefits = [
                benefit
                for benefit in benefits
                if "생활서비스" not in benefit["raw_text"]
            ]
            life_section = re.search(
                r"<h4[^>]*>생활서비스 5% 할인</h4>"
                r"([\s\S]*?)(?=<h[234]|$)",
                html,
                flags=re.IGNORECASE,
            )
            if life_section:
                life_text = _strip_tags(life_section.group(1))
                for category, keywords in (
                    ("convenience", "GS25, CU"),
                    ("cafe", "스타벅스, 이디야"),
                ):
                    benefits.append(
                        {
                            "category": category,
                            "benefit_group": "life_service",
                            "discount_type": "rate",
                            "discount_rate": "0.05",
                            "discount_amount": None,
                            "minimum_transaction_amount": 0,
                            "per_transaction_limit": None,
                            "daily_usage_limit": None,
                            "monthly_usage_limit": None,
                            "estimated_monthly_uses": None,
                            "category_monthly_limit": None,
                            "merchant_scope": keywords.split(", "),
                            "channel": "offline",
                            "condition_text": life_text,
                            "exclusion_text": "",
                            "raw_text": f"{keywords} 5% 할인 {life_text}",
                            "unsupported_conditions": [],
                        }
                    )
        return benefits

    @staticmethod
    def _service_limit_tiers(html, card_name):
        if "Deep Oil" not in card_name:
            return []
        text = _strip_tags(html)
        tiers = []
        for minimum, maximum, spending_limit in (
            (300000, 700000, 150000),
            (700000, None, 300000),
        ):
            range_text = (
                "30만원 이상 70만원 미만"
                if maximum is not None
                else "70만원 이상"
            )
            if range_text not in text:
                continue
            tiers.append(
                {
                    "benefit_group": "life_service",
                    "minimum_spending": minimum,
                    "maximum_spending": maximum,
                    "monthly_spending_limit": spending_limit,
                    "monthly_discount_limit": int(spending_limit * 0.05),
                    "monthly_usage_limit": None,
                    "raw_text": (
                        f"{range_text}: 생활서비스 월 이용금액 한도 "
                        f"{spending_limit}원"
                    ),
                }
            )
        return tiers

    @staticmethod
    def _specialized_benefits(card_name):
        common = {
            "minimum_transaction_amount": 0,
            "maximum_transaction_amount": None,
            "per_transaction_limit": None,
            "daily_benefit_limit": None,
            "daily_usage_limit": None,
            "monthly_usage_limit": None,
            "estimated_monthly_uses": None,
            "category_monthly_limit": None,
            "channel": "all",
            "condition_text": "",
            "exclusion_text": "",
            "unsupported_conditions": [],
        }
        if card_name == "신한카드 Simple Plan+":
            return [
                {
                    **common,
                    "category": category,
                    "benefit_group": "",
                    "discount_type": "rate",
                    "discount_rate": "0.015",
                    "discount_amount": None,
                    "merchant_scope": [],
                    "raw_text": "국내 이용금액 1.5% 결제일 할인",
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
        if card_name == "배민 신한카드 밥친구":
            return [
                {
                    **common,
                    "category": "food",
                    "benefit_group": "",
                    "discount_type": "rate",
                    "discount_rate": "0.05",
                    "discount_amount": None,
                    "category_monthly_limit": 30000,
                    "merchant_scope": ["배달의민족"],
                    "channel": "online",
                    "raw_text": (
                        "배달의민족 이용금액 5% 결제일 할인, "
                        "전월 20만원 이상 월 3만원 한도"
                    ),
                }
            ]
        if card_name == "알리익스프레스 신한카드":
            return [
                {
                    **common,
                    "category": "shopping",
                    "benefit_group": "ali_shopping",
                    "discount_type": "rate",
                    "discount_rate": "0.10",
                    "discount_amount": None,
                    "merchant_scope": ["알리익스프레스"],
                    "channel": "online",
                    "raw_text": (
                        "알리익스프레스 국내·해외 배송상품 10% 결제일 할인"
                    ),
                }
            ]
        if card_name == "신한카드 Edu Plan+":
            return [
                {
                    **common,
                    "category": "mart",
                    "benefit_group": "edu_mart",
                    "discount_type": "rate",
                    "discount_rate": "0.01",
                    "discount_amount": None,
                    "merchant_scope": ["홈플러스", "이마트", "롯데마트"],
                    "channel": "offline",
                    "raw_text": (
                        "홈플러스·이마트·롯데마트 오프라인 매장 1% 캐시백, "
                        "전월 50만원 이상 월 2천원 한도"
                    ),
                }
            ]
        if card_name == "신한카드 Unboxing":
            cashback_scopes = {
                "cafe": ["카페 노티드"],
                "convenience": ["CU", "GS25", "세븐일레븐", "이마트24"],
                "mart": [
                    "이마트",
                    "홈플러스",
                    "롯데마트",
                    "이마트 트레이더스",
                    "IKEA",
                ],
                "shopping": [
                    "쿠팡",
                    "11번가",
                    "G마켓",
                    "SSG.COM",
                    "롯데ON",
                    "롯데백화점",
                    "현대백화점",
                    "신세계백화점",
                    "롯데아울렛",
                    "현대아울렛",
                    "신세계아울렛",
                    "GS홈쇼핑",
                    "롯데홈쇼핑",
                    "현대홈쇼핑",
                    "CJ오쇼핑",
                    "올댓쇼핑",
                    "Tops몰",
                ],
            }
            benefits = [
                {
                    **common,
                    "category": category,
                    "benefit_group": "unboxing_cashback",
                    "discount_type": "rate",
                    "discount_rate": "0.10",
                    "discount_amount": None,
                    "minimum_transaction_amount": 30000,
                    "merchant_scope": merchant_scope,
                    "raw_text": (
                        "공식 대상 가맹점 3만원 이상 결제 건 10% 캐시백, "
                        "전월 실적별 통합 한도 적용"
                    ),
                }
                for category, merchant_scope in cashback_scopes.items()
            ]
            benefits.append(
                {
                    **common,
                    "category": "shopping",
                    "benefit_group": "unboxing_special",
                    "discount_type": "amount",
                    "discount_rate": None,
                    "discount_amount": 2500,
                    "maximum_transaction_amount": 30000,
                    "monthly_usage_limit": 6,
                    "estimated_monthly_uses": 6,
                    "merchant_scope": [
                        "신한 SOL페이 트렌드샵",
                        "네이버 플러스 멤버십",
                        "쿠팡 로켓와우",
                        "롯데오너스",
                        "몰테일",
                        "택배파인더",
                    ],
                    "channel": "online",
                    "raw_text": (
                        "공식 대상점 3만원 미만 결제 건당 2,500원 할인, "
                        "전월 실적별 월 2회·4회·6회 통합 제공"
                    ),
                }
            )
            return benefits
        if card_name == "신한카드 처음":
            today_scopes = {
                "food": [],
                "cafe": [
                    "스타벅스",
                    "블루보틀",
                    "엔제리너스",
                    "이디야",
                    "폴바셋",
                    "투썸플레이스",
                    "빽다방",
                ],
                "convenience": ["CU", "GS25", "이마트24", "세븐일레븐"],
                "shopping": ["쿠팡", "컬리"],
            }
            return [
                {
                    **common,
                    "category": category,
                    "benefit_group": "first_today",
                    "discount_type": "rate",
                    "discount_rate": "0.05",
                    "discount_amount": None,
                    "per_transaction_limit": 500,
                    "daily_benefit_limit": 1000,
                    "merchant_scope": merchant_scope,
                    "channel": (
                        "online"
                        if category == "shopping"
                        else "offline"
                    ),
                    "raw_text": (
                        "음식점·카페·편의점·온라인쇼핑 5% 적립, "
                        "1회 이용금액 최대 1만원 적용, 일 최대 1천포인트, "
                        "전월 실적별 월 통합 한도 적용"
                    ),
                }
                for category, merchant_scope in today_scopes.items()
            ]
        if card_name == "LG전자 The 구독케어 신한카드":
            return [
                {
                    **common,
                    "category": "shopping",
                    "benefit_group": "lg_subscription_discount",
                    "discount_type": "amount",
                    "discount_rate": None,
                    "discount_amount": 20000,
                    "monthly_usage_limit": 1,
                    "estimated_monthly_uses": 1,
                    "merchant_scope": ["LG전자"],
                    "channel": "online",
                    "raw_text": (
                        "LG전자 구독요금 자동납부 전월 실적별 월 최대 "
                        "1만3천원·1만6천원·2만원 결제일 할인"
                    ),
                },
                {
                    **common,
                    "category": "shopping",
                    "benefit_group": "lg_subscription_point",
                    "discount_type": "amount",
                    "discount_rate": None,
                    "discount_amount": 10000,
                    "minimum_transaction_amount": 70000,
                    "monthly_usage_limit": 1,
                    "estimated_monthly_uses": 1,
                    "merchant_scope": ["LG전자"],
                    "channel": "online",
                    "raw_text": (
                        "LG전자 구독요금 7만원 이상 자동납부 시 "
                        "월 1회 1만 마이신한포인트"
                    ),
                },
            ]
        if card_name == "K-패스 신한카드":
            services = (
                ("food", "online", ["배달의민족", "요기요"]),
                ("convenience", "offline", ["GS25", "CU"]),
                (
                    "cafe",
                    "offline",
                    ["스타벅스", "메가MGC커피", "매머드커피"],
                ),
                ("shopping", "offline", ["올리브영"]),
                ("shopping", "online", ["올리브영"]),
            )
            return [
                {
                    **common,
                    "category": category,
                    "benefit_group": "kpass_lifestyle",
                    "discount_type": "rate",
                    "discount_rate": "0.05",
                    "discount_amount": None,
                    "minimum_transaction_amount": 20000,
                    "per_transaction_limit": 3000,
                    "daily_usage_limit": 1,
                    "merchant_scope": merchant_scope,
                    "channel": channel,
                    "raw_text": (
                        "생활서비스 대상 가맹점 5% 할인, 건당 2만원 이상, "
                        "일 1회, 할인 전 이용금액 6만원까지 적용"
                    ),
                }
                for category, channel, merchant_scope in services
            ]
        return None

    @staticmethod
    def _specialized_service_limit_tiers(card_name):
        if card_name == "알리익스프레스 신한카드":
            return [
                {
                    "benefit_group": "ali_shopping",
                    "minimum_spending": minimum,
                    "maximum_spending": maximum,
                    "monthly_spending_limit": None,
                    "monthly_discount_limit": limit,
                    "monthly_usage_limit": None,
                    "raw_text": raw_text,
                }
                for minimum, maximum, limit, raw_text in (
                    (300000, 600000, 10000, "30만원 이상 60만원 미만 1만원"),
                    (600000, 1000000, 20000, "60만원 이상 100만원 미만 2만원"),
                    (1000000, None, 30000, "100만원 이상 3만원"),
                )
            ]
        if card_name == "신한카드 Edu Plan+":
            return [
                {
                    "benefit_group": "edu_mart",
                    "minimum_spending": 500000,
                    "maximum_spending": None,
                    "monthly_spending_limit": None,
                    "monthly_discount_limit": 2000,
                    "monthly_usage_limit": None,
                    "raw_text": "전월 50만원 이상 할인점 캐시백 한도 2천원",
                }
            ]
        if card_name == "신한카드 Unboxing":
            tiers = []
            for minimum, maximum, cashback_limit, usage_limit in (
                (400000, 800000, 10000, 2),
                (800000, 1200000, 25000, 4),
                (1200000, None, 50000, 6),
            ):
                tiers.extend(
                    [
                        {
                            "benefit_group": "unboxing_cashback",
                            "minimum_spending": minimum,
                            "maximum_spending": maximum,
                            "monthly_spending_limit": None,
                            "monthly_discount_limit": cashback_limit,
                            "monthly_usage_limit": None,
                            "raw_text": (
                                f"전월 {minimum}원 이상 10% 캐시백 "
                                f"월 {cashback_limit}원 한도"
                            ),
                        },
                        {
                            "benefit_group": "unboxing_special",
                            "minimum_spending": minimum,
                            "maximum_spending": maximum,
                            "monthly_spending_limit": None,
                            "monthly_discount_limit": usage_limit * 2500,
                            "monthly_usage_limit": usage_limit,
                            "raw_text": (
                                f"전월 {minimum}원 이상 건당 2,500원 "
                                f"월 {usage_limit}회"
                            ),
                        },
                    ]
                )
            return tiers
        if card_name == "신한카드 처음":
            return [
                {
                    "benefit_group": "first_today",
                    "minimum_spending": minimum,
                    "maximum_spending": maximum,
                    "monthly_spending_limit": None,
                    "monthly_discount_limit": limit,
                    "monthly_usage_limit": None,
                    "raw_text": raw_text,
                }
                for minimum, maximum, limit, raw_text in (
                    (300000, 500000, 5000, "30만원 이상 50만원 미만 5천포인트"),
                    (500000, 1000000, 10000, "50만원 이상 100만원 미만 1만포인트"),
                    (1000000, None, 20000, "100만원 이상 2만포인트"),
                )
            ]
        if card_name == "LG전자 The 구독케어 신한카드":
            discount_tiers = [
                {
                    "benefit_group": "lg_subscription_discount",
                    "minimum_spending": minimum,
                    "maximum_spending": maximum,
                    "monthly_spending_limit": None,
                    "monthly_discount_limit": limit,
                    "monthly_usage_limit": 1,
                    "raw_text": raw_text,
                }
                for minimum, maximum, limit, raw_text in (
                    (300000, 700000, 13000, "30만원 이상 70만원 미만 1만3천원"),
                    (700000, 1300000, 16000, "70만원 이상 130만원 미만 1만6천원"),
                    (1300000, None, 20000, "130만원 이상 2만원"),
                )
            ]
            point_tiers = [
                {
                    "benefit_group": "lg_subscription_point",
                    "minimum_spending": 700000,
                    "maximum_spending": None,
                    "monthly_spending_limit": None,
                    "monthly_discount_limit": 10000,
                    "monthly_usage_limit": 1,
                    "raw_text": "70만원 이상 7만원 자동납부 시 1만 포인트",
                }
            ]
            return discount_tiers + point_tiers
        if card_name == "K-패스 신한카드":
            return [
                {
                    "benefit_group": "kpass_lifestyle",
                    "minimum_spending": minimum,
                    "maximum_spending": maximum,
                    "monthly_spending_limit": None,
                    "monthly_discount_limit": limit,
                    "monthly_usage_limit": None,
                    "raw_text": raw_text,
                }
                for minimum, maximum, limit, raw_text in (
                    (300000, 600000, 7000, "30만원 이상 60만원 미만 7천원"),
                    (600000, None, 15000, "60만원 이상 1만5천원"),
                )
            ]
        return []

    @staticmethod
    def _benefit_tiers(html):
        tiers = []
        table_blocks = re.findall(
            r"<table[^>]*>([\s\S]*?)</table>",
            html,
            flags=re.IGNORECASE,
        )
        for table_html in table_blocks:
            table_text = _strip_tags(table_html)
            if not re.search(r"월 최대 [혜헤]택 한도", table_text):
                continue

            header_ranges = []
            for cell in re.findall(
                r"<th[^>]*>([\s\S]*?)</th>",
                table_html,
                flags=re.IGNORECASE,
            ):
                cell_text = _strip_tags(cell)
                match = re.search(
                    r"(\d+)만원 이상(?:\s*(\d+)만원 미만)?",
                    cell_text,
                )
                if match:
                    header_ranges.append(
                        (
                            int(match.group(1)) * 10000,
                            int(match.group(2)) * 10000
                            if match.group(2)
                            else None,
                        )
                    )

            total_row = next(
                (
                    row
                    for row in re.findall(
                        r"<tr[^>]*>([\s\S]*?)</tr>",
                        table_html,
                        flags=re.IGNORECASE,
                    )
                    if re.search(r"월 최대 [혜헤]택 한도", _strip_tags(row))
                ),
                None,
            )
            if not total_row:
                continue
            values = [
                _parse_korean_won(_strip_tags(cell))
                for cell in re.findall(
                    r"<td[^>]*>([\s\S]*?)</td>",
                    total_row,
                    flags=re.IGNORECASE,
                )[1:]
            ]
            if len(header_ranges) != len(values):
                continue

            parsed = [
                {
                    "scope": "card_total",
                    "minimum_spending": minimum,
                    "maximum_spending": maximum,
                    "monthly_discount_limit": limit,
                    "raw_text": table_text,
                }
                for (minimum, maximum), limit in zip(header_ranges, values)
                if limit > 0
            ]

            split_note = re.search(
                r"120만원 이상 150만원 미만[^\d]*(\d+만원)"
                r".*?150만원 이상 180만원 미만[^\d]*(\d+만\s*\d*천?원)",
                _strip_tags(html),
            )
            if split_note:
                parsed = [
                    tier
                    for tier in parsed
                    if not (
                        tier["minimum_spending"] == 1200000
                        and tier["maximum_spending"] == 1800000
                    )
                ]
                parsed.extend(
                    [
                        {
                            "scope": "card_total",
                            "minimum_spending": 1200000,
                            "maximum_spending": 1500000,
                            "monthly_discount_limit": _parse_korean_won(
                                split_note.group(1)
                            ),
                            "raw_text": split_note.group(0),
                        },
                        {
                            "scope": "card_total",
                            "minimum_spending": 1500000,
                            "maximum_spending": 1800000,
                            "monthly_discount_limit": _parse_korean_won(
                                split_note.group(2)
                            ),
                            "raw_text": split_note.group(0),
                        },
                    ]
                )

            tiers.extend(parsed)

        unique = {}
        for tier in tiers:
            key = (tier["scope"], tier["minimum_spending"])
            unique[key] = tier
        return sorted(unique.values(), key=lambda item: item["minimum_spending"])
