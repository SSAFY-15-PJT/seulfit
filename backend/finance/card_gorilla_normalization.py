import json
import re
from html import unescape

from .adapters.base import ProductPageParser


CATEGORY_KEYWORDS = {
    "delivery": (
        "배달앱",
        "배달의민족",
        "쿠팡이츠",
        "요기요",
        "땡겨요",
        "배달/주문",
    ),
    "cafe": (
        "카페",
        "커피",
        "스타벅스",
        "커피빈",
        "투썸",
        "메가커피",
    ),
    "convenience": (
        "편의점",
        "CU",
        "GS25",
        "세븐일레븐",
        "이마트24",
    ),
    "dining": (
        "음식점",
        "외식",
        "식음료",
        "패밀리레스토랑",
        "일반음식점",
        "푸드",
    ),
    "shopping": (
        "온라인쇼핑",
        "온라인 쇼핑",
        "온라인패션몰",
        "오픈마켓",
        "소셜커머스",
        "트렌디숍",
        "디지털콘텐츠",
        "멤버십",
        "간편결제",
        "네이버쇼핑",
        "스마트스토어",
        "브랜드스토어",
    ),
}

SUPPORTED_BENEFIT_CATEGORIES = (
    "cafe",
    "convenience",
    "dining",
    "delivery",
    "mart",
    "shopping",
)

UNIVERSAL_CATEGORY_PATTERNS = (
    "전 가맹점",
    "전가맹점",
    "국내 가맹점",
    "국내가맹점",
    "국내 전 가맹점",
    "국내전가맹점",
    "국내/외 전가맹점",
    "국내/외 모든 가맹점",
    "국내외 모든 가맹점",
    "국내외 가맹점",
    "모든 가맹점",
)

MERCHANT_ALIASES = {
    "delivery": {
        "배달의민족": ("배달의민족", "배달의 민족"),
        "쿠팡이츠": ("쿠팡이츠",),
        "요기요": ("요기요",),
        "땡겨요": ("땡겨요",),
    },
    "cafe": {
        "스타벅스": ("스타벅스",),
        "커피빈": ("커피빈",),
        "투썸플레이스": ("투썸플레이스",),
        "이디야커피": ("이디야커피", "이디야"),
        "메가MGC커피": ("메가MGC커피", "메가커피"),
        "컴포즈커피": ("컴포즈커피",),
        "폴바셋": ("폴바셋",),
        "할리스": ("할리스", "할리스커피"),
        "파리바게뜨": ("파리바게뜨",),
        "배스킨라빈스": ("배스킨라빈스",),
        "던킨": ("던킨",),
        "공차": ("공차",),
        "빽다방": ("빽다방",),
        "더벤티": ("더벤티",),
        "아티제": ("아티제",),
        "카페베네": ("카페베네",),
    },
    "convenience": {
        "CU": ("CU",),
        "GS25": ("GS25",),
        "세븐일레븐": ("세븐일레븐",),
        "이마트24": ("이마트24",),
    },
    "dining": {
        "아웃백스테이크하우스": ("아웃백스테이크하우스", "아웃백"),
        "VIPS": ("VIPS", "빕스"),
        "롯데리아": ("롯데리아",),
        "맘스터치": ("맘스터치",),
        "매드포갈릭": ("매드포갈릭",),
        "샐러디": ("샐러디",),
        "굽네치킨": ("굽네치킨",),
        "푸라닭치킨": ("푸라닭치킨", "푸라닭"),
        "죠스떡볶이": ("죠스떡볶이",),
        "청년다방": ("청년다방",),
    },
}

GENERIC_CATEGORY_SCOPES = {
    "cafe": (
        "커피 업종",
        "카페 업종",
        "커피전문점 업종",
        "커피/음료전문업종",
        "커피/음료전문점 업종",
    ),
    "convenience": ("편의점 업종",),
    "dining": (
        "음식점 업종",
        "일반음식점 업종",
        "식음료 업종",
        "한식, 양식, 일식, 중식",
    ),
}

ONLINE_CHANNEL_PATTERNS = (
    "온라인 결제건에 한",
    "온라인 결제건",
    "온라인에서 사용한 경우",
    "공식 홈페이지/앱을 통한 결제건에 한",
    "공식 홈페이지 및 앱을 통한 결제건에 한",
    "사이트/앱 직접 접속",
    "사이트 직접 접속",
    "앱을 통해서 접속 시에만",
    "온라인몰",
    "온라인 쇼핑몰",
)

OFFLINE_CHANNEL_PATTERNS = (
    "오프라인 결제건에 한",
    "오프라인 결제건",
    "오프라인 매장 현장 결제",
    "오프라인 매장",
    "오프라인 매장에서 사용한 경우",
    "현장 결제에 한함",
    "현장결제에 한함",
    "실물카드 및 삼성페이 결제",
)

PAYMENT_METHOD_PATTERNS = (
    "바코드 결제",
    "간편결제 제외",
    "간편 결제로 진행하는 경우 할인 적용 불가",
    "특정 결제수단",
    "배민페이",
    "사이렌오더",
    "삼성페이 결제",
)


def strip_html(value):
    parser = ProductPageParser("https://www.card-gorilla.com")
    parser.feed(str(value or ""))
    return unescape(parser.text)


def normalize_name(value):
    return re.sub(r"[^0-9a-z가-힣]", "", str(value or "").casefold())


def parse_annual_fee(value):
    text = str(value or "")
    amounts = []
    for token in re.findall(r"\[(.*?)\]", text):
        if "없음" in token:
            amounts.append(0)
            continue
        match = re.search(r"([\d,]+)\s*원?", token)
        if match:
            amounts.append(int(match.group(1).replace(",", "")))
    if amounts:
        return min(amounts)
    if "없음" in text:
        return 0
    return None


def parse_korean_amount(value):
    match = re.search(r"(\d+(?:\.\d+)?)\s*만\s*원", value)
    if match:
        return int(float(match.group(1)) * 10000)
    match = re.search(r"(\d+(?:\.\d+)?)\s*천\s*원", value)
    if match:
        return int(float(match.group(1)) * 1000)
    match = re.search(r"([\d,]+)\s*원", value)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def parse_card_monthly_discount_limit(text):
    text = str(text or "")
    sections = []
    for marker in (
        "통합 적립한도 안내",
        "월간 통합할인한도",
        "월 통합 적립한도",
        "월 통합 할인한도",
    ):
        if marker in text:
            sections.append(text[text.index(marker) : text.index(marker) + 1000])
    if not sections:
        return None

    candidates = []
    for section in sections:
        for match in re.finditer(
            r"([\d,.]+\s*(?:만|천)?\s*원|[\d,.]+\s*포인트)",
            section,
        ):
            token = match.group(1)
            if "포인트" in token:
                amount = int(
                    re.sub(r"[^\d]", "", token)
                    or 0
                )
            else:
                amount = parse_korean_amount(token)
            if amount is not None and amount <= 100000:
                candidates.append(amount)
    return max(candidates) if candidates else None


AMOUNT_PATTERN = r"[\d,.]+\s*(?:만|천)?\s*원"


def parse_minimum_transaction_amount(text):
    if re.search(rf"(?:건당|매출\s*건당).{{0,20}}{AMOUNT_PATTERN}\s*미만", text):
        return 0
    patterns = (
        rf"(?:건당|매출\s*건당|이용\s*건당)\s*({AMOUNT_PATTERN})\s*이상",
        rf"1회\s*이용\s*(?:금액)?\s*({AMOUNT_PATTERN})\s*이상",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return parse_korean_amount(match.group(1)) or 0
    return 0


def parse_category_monthly_limit(text):
    patterns = (
        rf"월\s*(?:할인|적립|캐시백)\s*한도\s*:?\s*({AMOUNT_PATTERN})",
        rf"월\s*(?:최대\s*)?({AMOUNT_PATTERN})\s*(?:까지|이내)?\s*"
        r"(?:할인|적립|캐시백)",
        rf"월\s*\d+\s*회\s*\(\s*({AMOUNT_PATTERN})\s*이내\s*\)",
        rf"({AMOUNT_PATTERN})\s*,?\s*\d+\s*회\s*한",
    )
    amounts = {
        amount
        for pattern in patterns
        for match in re.finditer(pattern, text)
        if (amount := parse_korean_amount(match.group(1))) is not None
    }
    return amounts.pop() if len(amounts) == 1 else None


def parse_usage_limit(text, period):
    match = re.search(
        rf"{period}\s*(?:(?:할인|적립|캐시백)\s*)?"
        rf"(?:횟수\s*:?\s*)?(\d+)\s*회",
        text,
    )
    return int(match.group(1)) if match else None


def benefit_categories(text):
    categories = [
        category
        for category, keywords in CATEGORY_KEYWORDS.items()
        if any(keyword.casefold() in text.casefold() for keyword in keywords)
    ]
    if categories:
        return categories
    if any(pattern in text for pattern in UNIVERSAL_CATEGORY_PATTERNS):
        return ["shopping"]
    return []


def extract_merchant_scope(category, text):
    if any(
        phrase in text
        for phrase in GENERIC_CATEGORY_SCOPES.get(category, ())
    ):
        return []
    return [
        canonical_name
        for canonical_name, aliases in MERCHANT_ALIASES.get(category, {}).items()
        if any(alias.casefold() in text.casefold() for alias in aliases)
    ]


def parse_channel_condition(text, allow_explicit_channel=True):
    has_online = any(pattern in text for pattern in ONLINE_CHANNEL_PATTERNS)
    has_offline = any(pattern in text for pattern in OFFLINE_CHANNEL_PATTERNS)
    unsupported = []

    has_channel_signal = has_online or has_offline
    if len(text) > 2500 and has_channel_signal:
        unsupported.append("mixed_channel_mapping")
        channel = "all"
    elif not allow_explicit_channel and has_channel_signal:
        unsupported.append("mixed_channel_mapping")
        channel = "all"
    elif has_online and has_offline:
        unsupported.append("mixed_channel_mapping")
        channel = "all"
    elif has_online:
        channel = "online"
    elif has_offline:
        channel = "offline"
    else:
        channel = "all"

    if any(pattern in text for pattern in PAYMENT_METHOD_PATTERNS):
        unsupported.append("payment_method_condition")
    return channel, unsupported


def parse_benefit(entry):
    summary_text = " ".join(
        part
        for part in (
            str(entry.get("title") or ""),
            str(entry.get("comment") or ""),
        )
        if part
    )
    raw_text = " ".join(
        part
        for part in (
            str(entry.get("title") or ""),
            str(entry.get("comment") or ""),
            strip_html(entry.get("info")),
        )
        if part
    )
    categories = benefit_categories(summary_text)
    categories_from_summary = bool(categories)
    detail_text = strip_html(entry.get("info"))
    if not categories:
        categories = benefit_categories(detail_text[:500])
    rate_match = re.search(
        r"(\d+(?:\.\d+)?)\s*%\s*(?:할인|캐시백|적립)",
        summary_text,
    ) or re.search(
        r"(\d+(?:\.\d+)?)\s*%\s*(?:할인|캐시백|적립)",
        detail_text,
    )
    amount_match = (
        None
        if rate_match
        else re.search(
            r"(?<!최대\s)([\d,.]+\s*(?:만|천)?\s*원)\s*(?:할인|캐시백)",
            summary_text,
        )
        or re.search(
            r"(?<!최대\s)([\d,.]+\s*(?:만|천)?\s*원)\s*(?:할인|캐시백)",
            detail_text,
        )
    )
    if not categories or (not rate_match and not amount_match):
        return []

    per_transaction_limit = None
    limit_match = re.search(
        r"(?:1회|건당|매출\s*건당)[^.!]{0,40}?최대\s*"
        r"([\d,.]+\s*(?:만|천)?\s*원)",
        summary_text,
    ) or re.search(
        r"(?:1회|건당|매출\s*건당)[^.!]{0,40}?최대\s*"
        r"([\d,.]+\s*(?:만|천)?\s*원)",
        detail_text,
    )
    if limit_match:
        per_transaction_limit = parse_korean_amount(limit_match.group(1))

    if len(categories) == 1:
        minimum_transaction_amount = parse_minimum_transaction_amount(raw_text)
        category_monthly_limit = parse_category_monthly_limit(raw_text)
        monthly_usage_limit = parse_usage_limit(raw_text, "월")
        daily_usage_limit = parse_usage_limit(raw_text, "일")
    else:
        minimum_transaction_amount = 0
        category_monthly_limit = None
        monthly_usage_limit = None
        daily_usage_limit = None
        per_transaction_limit = None

    discount_type = "rate" if rate_match else "amount"
    discount_rate = (
        str(float(rate_match.group(1)) / 100) if rate_match else None
    )
    discount_amount = (
        parse_korean_amount(amount_match.group(1)) if amount_match else None
    )
    channel_context = f"{summary_text} {detail_text[:500]}"
    channel, channel_conditions = parse_channel_condition(
        channel_context,
        allow_explicit_channel=(
            categories_from_summary
            and not any(
                marker in summary_text
                for marker in ("선택", "택 1", "옵션", "패키지")
            )
        ),
    )
    return [
        {
            "category": category,
            "benefit_group": "",
            "discount_type": discount_type,
            "discount_rate": discount_rate,
            "discount_amount": discount_amount,
            "minimum_transaction_amount": minimum_transaction_amount,
            "maximum_transaction_amount": None,
            "per_transaction_limit": per_transaction_limit,
            "daily_benefit_limit": None,
            "daily_usage_limit": daily_usage_limit,
            "monthly_usage_limit": monthly_usage_limit,
            "estimated_monthly_uses": None,
            "category_monthly_limit": category_monthly_limit,
            "merchant_scope": extract_merchant_scope(category, raw_text),
            "channel": channel,
            "condition_text": raw_text,
            "exclusion_text": "",
            "raw_text": raw_text,
            "unsupported_conditions": [
                "source_review_required",
                *channel_conditions,
            ],
        }
        for category in categories
    ]


def parse_card_gorilla_payload(payload):
    detail = payload.get("detail") or {}
    corp = detail.get("corp") or {}
    if isinstance(corp, str):
        corp = json.loads(corp)
    image = detail.get("card_img") or {}
    if isinstance(image, str):
        image = {"url": image}

    benefits = []
    raw_parts = []
    for entry in detail.get("key_benefit") or []:
        raw_text = " ".join(
            part
            for part in (
                str(entry.get("title") or ""),
                str(entry.get("comment") or ""),
                strip_html(entry.get("info")),
            )
            if part
        )
        raw_parts.append(raw_text)
        benefits.extend(parse_benefit(entry))

    source_url = payload.get("detail_page_url") or payload.get("api_source_url")
    name = detail.get("name") or payload.get("ranking_summary", {}).get("name", "")
    return {
        "external_id": str(payload.get("external_id") or detail.get("idx") or ""),
        "issuer": corp.get("name") or payload.get("ranking_summary", {}).get(
            "issuer", ""
        ),
        "provider": corp.get("name") or "카드고릴라",
        "source_channel": "card_gorilla",
        "card_type": payload.get("card_type", ""),
        "name": name,
        "source_url": source_url,
        "annual_fee": parse_annual_fee(detail.get("annual_fee_basic")),
        "annual_fee_source_url": "",
        "previous_month_requirement": int(detail.get("pre_month_money") or 0),
        "monthly_discount_limit": parse_card_monthly_discount_limit(raw_text),
        "raw_text": "\n".join(raw_parts) or name,
        "benefits": benefits,
        "benefit_tiers": [],
        "service_limit_tiers": [],
        "review_reasons": [
            "카드고릴라 보조 출처 데이터로 공식 카드사 자료 검증 필요",
            "복잡한 통합 한도와 제외 조건 수동 검수 필요",
        ],
        "images": (
            [{"source_url": image["url"], "alt_text": f"{name} 카드 이미지"}]
            if image.get("url")
            else []
        ),
    }
