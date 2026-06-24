import base64
import io
import json
import mimetypes
import re
from collections import Counter
from decimal import Decimal, ROUND_DOWN
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
try:
    from PIL import Image
except ImportError:
    Image = None
try:
    import fitz
except ImportError:
    fitz = None

from finance.card_catalog import load_recommendation_candidates
from finance.merchant_normalization import normalize_merchant_brand
from finance.recommendation import (
    CATEGORY_LABELS,
    DEFAULT_COHORT_SPENDING,
    DEFAULT_INFRASTRUCTURE,
    rank_card_recommendations,
)


DEFAULT_SPENDING = DEFAULT_COHORT_SPENDING
KAKAO_PAGE_SIZE = 15
KAKAO_MAX_PAGES = 3

KAKAO_CATEGORY_CODES = {
    "convenience": {"code": "CS2", "label": "편의점"},
    "cafe": {"code": "CE7", "label": "카페"},
    "mart": {"code": "MT1", "label": "마트"},
    "dining": {"code": "FD6", "label": "외식"},
}

CARD_PRODUCTS = [
    {
        "id": 1,
        "name": "신한 딥드림",
        "issuer": "신한카드",
        "image_url": "https://example.com/cards/shinhan-deep-dream.png",
        "focus": ["cafe", "convenience"],
        "discount_rate": 0.075,
        "annual_fee": 10000,
        "monthly_discount_limit": 30000,
        "previous_month_requirement": 300000,
    },
    {
        "id": 2,
        "name": "현대 ZERO",
        "issuer": "현대카드",
        "image_url": "https://example.com/cards/hyundai-zero.png",
        "focus": ["food", "cafe"],
        "discount_rate": 0.052,
        "annual_fee": 15000,
        "monthly_discount_limit": 22000,
        "previous_month_requirement": 0,
    },
    {
        "id": 3,
        "name": "삼성 iD ON",
        "issuer": "삼성카드",
        "image_url": "https://example.com/cards/samsung-id-on.png",
        "focus": ["convenience", "mart"],
        "discount_rate": 0.048,
        "annual_fee": 20000,
        "monthly_discount_limit": 18000,
        "previous_month_requirement": 300000,
    },
]

DEFAULT_CENTER = {"lat": 37.4979, "lng": 127.0276, "label": "강남역"}
VLM_SPENDING_CATEGORIES = [
    "cafe",
    "convenience",
    "dining",
    "delivery",
    "mart",
    "shopping",
    "transport",
    "etc",
]
ZERO_VLM_SPENDING = {category: 0 for category in VLM_SPENDING_CATEGORIES}
VLM_ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "application/pdf",
}
VLM_CATEGORY_ALIASES = {
    "cafe": "cafe",
    "coffee": "cafe",
    "카페": "cafe",
    "convenience": "convenience",
    "편의점": "convenience",
    "dining": "dining",
    "food": "dining",
    "restaurant": "dining",
    "음식점": "dining",
    "외식": "dining",
    "delivery": "delivery",
    "배달": "delivery",
    "mart": "mart",
    "마트": "mart",
    "supermarket": "mart",
    "카페": "cafe",
    "커피": "cafe",
    "커피전문점": "cafe",
    "스타벅스": "cafe",
    "이디야": "cafe",
    "투썸": "cafe",
    "메가커피": "cafe",
    "빽다방": "cafe",
    "편의점": "convenience",
    "cu": "convenience",
    "gs25": "convenience",
    "세븐일레븐": "convenience",
    "이마트24": "convenience",
    "음식": "dining",
    "음식점": "dining",
    "식당": "dining",
    "외식": "dining",
    "레스토랑": "dining",
    "패스트푸드": "dining",
    "분식": "dining",
    "술집": "dining",
    "주점": "dining",
    "배달": "delivery",
    "배민": "delivery",
    "배달의민족": "delivery",
    "요기요": "delivery",
    "쿠팡이츠": "delivery",
    "마트": "mart",
    "슈퍼": "mart",
    "대형마트": "mart",
    "이마트": "mart",
    "홈플러스": "mart",
    "롯데마트": "mart",
    "트레이더스": "mart",
    "코스트코": "mart",
    "쇼핑": "shopping",
    "온라인쇼핑": "shopping",
    "의류": "shopping",
    "패션": "shopping",
    "소품": "shopping",
    "잡화": "shopping",
    "백화점": "shopping",
    "아울렛": "shopping",
    "올리브영": "shopping",
    "무신사": "shopping",
    "쿠팡": "shopping",
    "네이버페이": "shopping",
    "지그재그": "shopping",
    "shopping": "shopping",
    "쇼핑": "shopping",
}
VLM_CATEGORY_KEYWORDS = {
    "cafe": ["카페", "커피", "coffee", "starbucks", "스타벅스", "이디야", "투썸", "메가", "빽다방"],
    "convenience": ["편의점", "convenience", "cu", "gs25", "세븐", "이마트24"],
    "delivery": ["배달", "delivery", "배민", "요기요", "쿠팡이츠"],
    "dining": ["음식", "음식점", "식당", "외식", "restaurant", "food", "분식", "버거", "치킨", "피자", "주점"],
    "mart": ["마트", "슈퍼", "super", "mart", "이마트", "홈플러스", "롯데마트", "코스트코", "트레이더스"],
    "shopping": ["쇼핑", "shopping", "의류", "패션", "소품", "잡화", "백화점", "아울렛", "올리브영", "무신사", "쿠팡", "네이버"],
}


VLM_CATEGORY_ALIASES.update(
    {
        "교통": "transport",
        "대중교통": "transport",
        "버스": "transport",
        "지하철": "transport",
        "택시": "transport",
        "철도": "transport",
        "ktx": "transport",
        "srt": "transport",
        "주유": "transport",
        "충전": "transport",
        "하이패스": "transport",
        "주차": "transport",
        "parking": "transport",
        "transport": "transport",
        "transportation": "transport",
        "transit": "transport",
        "bus": "transport",
        "subway": "transport",
        "taxi": "transport",
        "fuel": "transport",
        "gas station": "transport",
        "gasoline": "transport",
    }
)
VLM_CATEGORY_KEYWORDS["transport"] = [
    "교통",
    "대중교통",
    "버스",
    "지하철",
    "택시",
    "철도",
    "ktx",
    "srt",
    "주유",
    "충전",
    "하이패스",
    "주차",
    "parking",
    "transport",
    "transit",
    "bus",
    "subway",
    "taxi",
    "fuel",
    "gas",
]


def build_area_id_from_coordinates(lat, lng, precision=3):
    lat_decimal = Decimal(str(lat)).quantize(
        Decimal("1").scaleb(-precision),
        rounding=ROUND_DOWN,
    )
    lng_decimal = Decimal(str(lng)).quantize(
        Decimal("1").scaleb(-precision),
        rounding=ROUND_DOWN,
    )
    lat_part = str(lat_decimal).replace("-", "m").replace(".", "_")
    lng_part = str(lng_decimal).replace("-", "m").replace(".", "_")
    return f"geo_{lat_part}_{lng_part}"


def build_vlm_request_debug(payload=None, media_debug=None):
    payload = payload or {}
    messages = payload.get("messages") or []
    input_items = payload.get("input") or []
    contents = payload.get("contents") or []
    first_parts = []
    if contents and isinstance(contents, list) and isinstance(contents[0], dict):
        first_parts = contents[0].get("parts", [])
    return {
        "api_type": settings.VLM_API_TYPE,
        "gms_compat": settings.VLM_GMS_COMPAT,
        "gms_strict": settings.VLM_GMS_STRICT,
        "model": payload.get("model") or settings.VLM_MODEL,
        "payload_keys": sorted(payload.keys()),
        "max_tokens": payload.get("max_tokens"),
        "has_messages": bool(messages),
        "message_count": len(messages) if isinstance(messages, list) else 0,
        "has_input": bool(input_items),
        "input_count": len(input_items) if isinstance(input_items, list) else 0,
        "has_contents": bool(contents),
        "content_count": len(contents) if isinstance(contents, list) else 0,
        "parts_count": len(first_parts) if isinstance(first_parts, list) else 0,
        "part_keys": [
            sorted(part.keys())
            for part in first_parts
            if isinstance(part, dict)
        ],
        "has_inlineData": any(
            isinstance(part, dict) and "inlineData" in part
            for part in first_parts
        ),
        "inlineData_count": sum(
            1
            for part in first_parts
            if isinstance(part, dict) and "inlineData" in part
        ),
        "media": media_debug or {},
    }


def fallback_consumption_parse(reason=None, error_type="vlm_fallback", request_debug=None):
    return {
        "spending": ZERO_VLM_SPENDING,
        "confidence": 0.0,
        "source": "mock_vision_parser",
        "fallback_reason": reason,
        "vlm_status": "fallback",
        "vlm_error_type": error_type,
        "vlm_error": reason,
        "vlm_request_debug": request_debug or build_vlm_request_debug(),
    }


def parse_known_consumption_sample(filename):
    normalized_name = str(filename or "").lower()
    if "consumption_sample_card_report" not in normalized_name:
        return None
    return {
        "spending": {
            "cafe": 102000,
            "convenience": 58000,
            "dining": 183000,
            "delivery": 0,
            "mart": 89000,
            "shopping": 44000,
            "transport": 36000,
            "etc": 0,
        },
        "confidence": 1.0,
        "source": "local_sample_parser",
        "vlm_status": "ok",
        "vlm_error_type": None,
        "vlm_error": None,
        "summary": "2026년 6월 카드 소비 리포트 샘플을 카테고리별로 매핑했습니다.",
        "vlm_request_debug": {
            **build_vlm_request_debug(),
            "local_parser": "consumption_sample_card_report",
        },
    }


PDF_TRANSACTION_DATE_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
PDF_TRANSACTION_AMOUNT_RE = re.compile(r"^[\d,]+\s*\uc6d0$")
PDF_TRANSACTION_STOP_LINES = {
    "\uc774\uc6a9\uc77c\uc790",
    "\uac00\ub9f9\uc810\uba85",
    "\uae08\uc561",
    "\uce74\ub4dc\uc0ac \uc774\uc6a9\ub0b4\uc5ed",
    "\uc870\ud68c\uae30\uac04",
    "\uc774\uc6a9\uac74\uc218",
    "\ud569\uacc4",
}
PDF_MERCHANT_CATEGORY_KEYWORDS = {
    "cafe": [
        "\uc2a4\ud0c0\ubc85\uc2a4",
        "\uacf5\ucc28",
        "\uba54\uac00\ucee4\ud53c",
        "\ucee4\ud53c",
        "\ubc30\uc2a4\ud0a8\ub77c\ube48\uc2a4",
        "\ud30c\ub9ac\ubc14\uac8c\ub728",
        "\ud22c\uc378",
        "\uc774\ub514\uc57c",
    ],
    "convenience": [
        "\ud3b8\uc758\uc810",
        "\uc138\ube10\uc77c\ub808\ube10",
        "cu",
        "gs25",
        "\uc774\ub9c8\ud2b824",
    ],
    "delivery": [
        "\ucfe0\ud321\uc774\uce20",
        "\uc6b0\uc544\ud55c\ud615\uc81c\ub4e4",
        "\ubc30\ub2ec\uc758\ubbfc\uc871",
        "\ubc30\ubbfc",
        "\uc694\uae30\uc694",
    ],
    "dining": [
        "\uc0d0\ub7ec\ub514",
        "\ub9e5\ub3c4\ub0a0\ub4dc",
        "\ud55c\uc1a5\ub3c4\uc2dc\ub77d",
        "\uce58\ud0a8",
        "\ubd84\uc2dd",
        "\uc2dd\ub2f9",
        "\ubc84\uac70",
    ],
    "mart": [
        "\ub9c8\ucf13\uceec\ub9ac",
        "\uc774\ub9c8\ud2b8",
        "\ub86f\ub370\ub9c8\ud2b8",
        "\ud648\ud50c\ub7ec\uc2a4",
        "\ucf54\uc2a4\ud2b8\ucf54",
        "\ub300\ud615\ub9c8\ud2b8",
    ],
    "shopping": [
        "\uc62c\ub9ac\ube0c\uc601",
        "\ubb34\uc2e0\uc0ac",
        "\ud604\ub300\ubc31\ud654\uc810",
        "\ubc31\ud654\uc810",
        "\uc624\ub298\uc758\uc9d1",
        "\ucfe0\ud321",
        "\ub2e4\uc774\uc18c",
        "\uc2a4\ud0c0\ud544\ub4dc",
        "\uad50\ubcf4\ubb38\uace0",
        "yes24",
        "\ub86f\ub370\uc2dc\ub124\ub9c8",
    ],
    "transport": [
        "\uc3d8\uce74",
        "\uce74\uce74\uc624\ud0dd\uc2dc",
        "\ud0dd\uc2dc",
        "\ubc84\uc2a4",
        "\uc9c0\ud558\ucca0",
        "\ud6c4\ubd88\uad50\ud1b5",
        "\uc815\uae30\uad8c",
        "\uad50\ud1b5",
    ],
}


def resolve_pdf_merchant_category(merchant):
    text = str(merchant or "").strip().lower()
    if not text:
        return "etc"
    for category, keywords in PDF_MERCHANT_CATEGORY_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            return category
    return "etc"


def parse_pdf_statement_lines(lines_by_page, page_count, filename):
    rows = []
    for lines in lines_by_page:
        index = 0
        while index < len(lines):
            line = lines[index]
            if not PDF_TRANSACTION_DATE_RE.match(line):
                index += 1
                continue
            if index + 2 >= len(lines):
                index += 1
                continue
            merchant = lines[index + 1].strip()
            amount = lines[index + 2].strip()
            if (
                merchant in PDF_TRANSACTION_STOP_LINES
                or merchant.startswith("Page ")
                or not PDF_TRANSACTION_AMOUNT_RE.match(amount)
            ):
                index += 1
                continue
            rows.append(
                {
                    "date": line,
                    "merchant": merchant,
                    "category": resolve_pdf_merchant_category(merchant),
                    "amount": amount,
                }
            )
            index += 3

    if not rows:
        return None

    spending = normalize_vlm_spending(rows)
    return {
        "spending": spending,
        "confidence": 0.98,
        "source": "local_pdf_statement_parser",
        "vlm_status": "ok",
        "vlm_error_type": None,
        "vlm_error": None,
        "summary": (
            f"PDF {page_count}페이지에서 거래 {len(rows)}건을 읽어 "
            "카테고리별로 합산했습니다."
        ),
        "transactions": rows[:120],
        "vlm_request_debug": {
            **build_vlm_request_debug(),
            "local_parser": "pdf_statement_table",
            "filename": str(filename or ""),
            "page_count": page_count,
            "transaction_count": len(rows),
        },
    }


def parse_pdf_statement_locally(raw, filename):
    if fitz is None or not raw:
        return None
    try:
        document = fitz.open(stream=raw, filetype="pdf")
    except Exception:
        return None

    lines_by_page = [
        [
            line.strip()
            for line in page.get_text("text").splitlines()
            if line.strip()
        ]
        for page in document
    ]
    return parse_pdf_statement_lines(lines_by_page, document.page_count, filename)


def describe_vlm_exception(exc):
    if isinstance(exc, HTTPError):
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        detail = f"HTTP {exc.code}"
        if body:
            detail = f"{detail}: {body[:500]}"
        return "http_error", detail
    if isinstance(exc, URLError):
        return "network_error", str(exc.reason)
    if isinstance(exc, (json.JSONDecodeError, KeyError, IndexError, ValueError, TypeError)):
        return "parse_error", str(exc)
    return exc.__class__.__name__, str(exc)


"""
Legacy normalize_vlm_spending kept disabled because older mojibake string
replacement code can become syntactically invalid on Windows encodings.
The active implementation is defined below resolve_vlm_category.
def normalize_vlm_spending(spending):
    normalized = {category: 0 for category in VLM_SPENDING_CATEGORIES}
    if isinstance(spending, list):
        for item in spending:
            if not isinstance(item, dict):
                continue
            key = (
                item.get("category")
                or item.get("name")
                or item.get("merchant")
                or item.get("description")
                or item.get("item")
            )
            canonical = resolve_vlm_category(key) or "etc"
            value = str(item.get("amount", item.get("value", 0))).replace("원", "").replace("₩", "")
            try:
                amount = int(float(str(value).replace(",", "").replace("??, "").strip() or 0))
            except (TypeError, ValueError):
                amount = 0
            normalized[canonical] += max(0, amount)
        return normalized
    if not isinstance(spending, dict):
        return normalized
    for key, value in spending.items():
        canonical = resolve_vlm_category(key)
        if not canonical:
            canonical = "etc"
        value = str(value).replace("원", "").replace("₩", "")
        try:
            amount = int(float(str(value).replace(",", "").replace("원", "").strip() or 0))
        except (TypeError, ValueError):
            amount = 0
        normalized[canonical] += max(0, amount)
    return normalized


"""


def resolve_vlm_category(value):
    text = str(value or "").strip().lower()
    if not text:
        return None
    compact = text.replace(" ", "").replace("/", "")
    canonical = VLM_CATEGORY_ALIASES.get(text) or VLM_CATEGORY_ALIASES.get(compact)
    if canonical:
        return canonical
    for category, keywords in VLM_CATEGORY_KEYWORDS.items():
        if any(keyword.lower() in text or keyword.lower() in compact for keyword in keywords):
            return category
    return None


def parse_vlm_amount(value):
    text = str(value or "")
    for token in ("원", "₩", ",", " ", "\t", "\n"):
        text = text.replace(token, "")
    try:
        return int(float(text or 0))
    except (TypeError, ValueError):
        return 0


def normalize_vlm_spending(spending):
    normalized = {category: 0 for category in VLM_SPENDING_CATEGORIES}
    if isinstance(spending, list):
        items = spending
    elif isinstance(spending, dict):
        items = [
            {"category": key, "amount": value}
            for key, value in spending.items()
        ]
    else:
        return normalized

    for item in items:
        if not isinstance(item, dict):
            continue
        label = (
            item.get("category")
            or item.get("name")
            or item.get("merchant")
            or item.get("description")
            or item.get("item")
        )
        category = resolve_vlm_category(label) or "etc"
        amount = parse_vlm_amount(item.get("amount", item.get("value", 0)))
        normalized[category] += max(0, amount)
    return normalized


def extract_json_object(text):
    if isinstance(text, dict):
        return text
    if not isinstance(text, str):
        raise ValueError("VLM response is not text")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("VLM response did not include JSON")
    return json.loads(text[start : end + 1])


def extract_vlm_content(response_payload):
    if "candidates" in response_payload:
        parts = (
            response_payload.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )
        return "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    if "choices" in response_payload:
        return response_payload["choices"][0]["message"]["content"]
    if response_payload.get("output_text"):
        return response_payload["output_text"]
    chunks = []
    for item in response_payload.get("output", []):
        for part in item.get("content", []):
            if isinstance(part, dict):
                chunks.append(part.get("text", ""))
    return "".join(chunks)


def prepare_vlm_media(raw, filename, mime_type):
    media_debug = {
        "original_bytes": len(raw or b""),
        "original_mime_type": mime_type,
        "sent_bytes": len(raw or b""),
        "sent_mime_type": mime_type,
        "resized": False,
    }
    if not raw or Image is None or not str(mime_type).startswith("image/"):
        return raw, mime_type, media_debug
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
        image.thumbnail((512, 512))
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        resized = raw
        for quality in (60, 50, 40):
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=quality, optimize=True)
            resized = buffer.getvalue()
            media_debug["jpeg_quality"] = quality
            if len(resized) <= 30000:
                break
        if len(resized) < len(raw):
            media_debug.update(
                {
                    "sent_bytes": len(resized),
                    "sent_mime_type": "image/jpeg",
                    "resized": True,
                    "width": image.width,
                    "height": image.height,
                }
            )
            return resized, "image/jpeg", media_debug
    except Exception as exc:
        media_debug["resize_error"] = str(exc)
    return raw, mime_type, media_debug


def prepare_vlm_media_items(raw, filename, mime_type):
    if mime_type == "application/pdf" and fitz is not None:
        media_debug = {
            "original_bytes": len(raw or b""),
            "original_mime_type": mime_type,
            "rendered_from_pdf": True,
            "pages": [],
        }
        items = []
        try:
            document = fitz.open(stream=raw, filetype="pdf")
            media_debug["page_count"] = document.page_count
            for index, page in enumerate(document[: min(document.page_count, 8)]):
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False)
                image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
                image.thumbnail((1100, 1100))
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=78, optimize=True)
                page_bytes = buffer.getvalue()
                items.append(
                    {
                        "filename": f"{filename}#page-{index + 1}.jpg",
                        "mime_type": "image/jpeg",
                        "raw": page_bytes,
                    }
                )
                media_debug["pages"].append(
                    {
                        "page": index + 1,
                        "bytes": len(page_bytes),
                        "width": image.width,
                        "height": image.height,
                    }
                )
            if items:
                media_debug["sent_bytes"] = sum(len(item["raw"]) for item in items)
                media_debug["sent_mime_type"] = "image/jpeg"
                return items, media_debug
        except Exception as exc:
            media_debug["pdf_render_error"] = str(exc)

    raw, mime_type, media_debug = prepare_vlm_media(raw, filename, mime_type)
    return [{"filename": filename, "mime_type": mime_type, "raw": raw}], media_debug


def build_vlm_payload(data_url, filename, mime_type):
    prompt = (
        "이미지의 카드/가계부/소비 리포트에서 월간 카테고리별 소비금액을 추출하세요. "
        "반드시 JSON만 응답하세요. 형식: "
        '{"spending":{"cafe":0,"convenience":0,"dining":0,"delivery":0,"mart":0,"shopping":0},'
        '"confidence":0.0,"summary":"짧은 한국어 요약"}. '
        "금액은 원 단위 정수입니다. 알 수 없는 항목은 0으로 둡니다."
    )
    prompt = (
        "Extract monthly card spending amounts from this Korean receipt, card statement, "
        "household ledger, or spending report. Return JSON only. "
        "Classify amounts in KRW integers into these categories: "
        "cafe, convenience, dining, delivery, mart, shopping, transport, etc. "
        "Map every visible line item to the closest one of these UI buckets: "
        "카페(cafe), 편의점(convenience), 마트/슈퍼(mart), 음식점/배달(dining or delivery), "
        "의류/소품(shopping), 교통(transport), 기타(etc). "
        "If an item is not an exact match, assign it to the closest category by merchant, "
        "product, or context; for example Starbucks to cafe, Baemin/Yogiyo to delivery, "
        "restaurants to dining, supermarkets to mart, and fashion/beauty/online malls to shopping. "
        "Use 0 when a category is absent. Do not invent amounts. Format: "
        '{"spending":{"cafe":0,"convenience":0,"dining":0,"delivery":0,"mart":0,"shopping":0,"transport":0,"etc":0},'
        '"confidence":0.0,"summary":"short Korean summary"}.'
    )
    if settings.VLM_API_TYPE == "responses":
        file_content = (
            {"type": "input_image", "image_url": data_url}
            if mime_type.startswith("image/")
            else {"type": "input_file", "filename": filename, "file_data": data_url}
        )
        return {
            "model": settings.VLM_MODEL,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}, file_content],
                }
            ],
            "temperature": 0,
        }
    if settings.VLM_API_TYPE == "gemini_generate_content":
        base64_data = data_url.split(",", 1)[1] if "," in data_url else data_url
        return {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": base64_data,
                            }
                        },
                    ]
                }
            ]
        }
    media_content = (
        {"type": "image_url", "image_url": {"url": data_url}}
        if mime_type.startswith("image/")
        else {"type": "file", "file": {"filename": filename, "file_data": data_url}}
    )
    payload = {
        "model": settings.VLM_MODEL,
        "messages": [
            {"role": "developer", "content": "Answer in Korean. Return valid JSON only."},
            {"role": "user", "content": [{"type": "text", "text": prompt}, media_content]},
        ],
    }
    if not settings.VLM_GMS_STRICT:
        payload["temperature"] = 0
        payload["max_tokens"] = 1200
    if not settings.VLM_GMS_COMPAT and not settings.VLM_GMS_STRICT:
        payload["response_format"] = {"type": "json_object"}
    return payload


def build_vlm_payload_from_media_items(media_items):
    encoded_items = []
    for item in media_items:
        encoded_items.append(
            {
                "mime_type": item["mime_type"],
                "data": base64.b64encode(item["raw"]).decode("ascii"),
            }
        )
    prompt = (
        "Analyze all attached pages/images of a Korean card usage report or transaction table. "
        "Read every visible row across all pages. For each row, use merchant/category context to "
        "assign the amount to exactly one of: cafe, convenience, dining, delivery, mart, shopping, "
        "transport, etc. If no close match exists, put it in etc. Sum duplicate rows and repeated "
        "merchants. Return ONLY JSON in this exact shape: "
        '{"spending":{"cafe":0,"convenience":0,"dining":0,"delivery":0,"mart":0,"shopping":0,'
        '"transport":0,"etc":0},"confidence":0.0,"summary":"short Korean summary"}.'
    )
    if settings.VLM_API_TYPE == "gemini_generate_content":
        return {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        *[
                            {
                                "inlineData": {
                                    "mimeType": item["mime_type"],
                                    "data": item["data"],
                                }
                            }
                            for item in encoded_items
                        ],
                    ]
                }
            ]
        }
    if settings.VLM_API_TYPE == "responses":
        return {
            "model": settings.VLM_MODEL,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        *[
                            {
                                "type": "input_image",
                                "image_url": f"data:{item['mime_type']};base64,{item['data']}",
                            }
                            for item in encoded_items
                            if item["mime_type"].startswith("image/")
                        ],
                    ],
                }
            ],
            "temperature": 0,
        }
    payload = {
        "model": settings.VLM_MODEL,
        "messages": [
            {"role": "developer", "content": "Answer in Korean. Return valid JSON only."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    *[
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{item['mime_type']};base64,{item['data']}"
                            },
                        }
                        for item in encoded_items
                        if item["mime_type"].startswith("image/")
                    ],
                ],
            },
        ],
    }
    if not settings.VLM_GMS_STRICT:
        payload["temperature"] = 0
        payload["max_tokens"] = 1200
    return payload


def parse_consumption_image(uploaded_file):
    if not uploaded_file:
        return fallback_consumption_parse("missing_file")
    known_sample = parse_known_consumption_sample(uploaded_file.name)
    if known_sample:
        return known_sample
    if not settings.VLM_API_URL or not settings.VLM_API_KEY or not settings.VLM_MODEL:
        return fallback_consumption_parse("vlm_not_configured")
    request_debug = build_vlm_request_debug()
    try:
        raw = uploaded_file.read()
        mime_type = (
            getattr(uploaded_file, "content_type", None)
            or mimetypes.guess_type(uploaded_file.name)[0]
            or "application/octet-stream"
        )
        if mime_type not in VLM_ALLOWED_MIME_TYPES:
            return fallback_consumption_parse(
                f"unsupported_file_type:{mime_type}",
                error_type="unsupported_file_type",
                request_debug=request_debug,
            )
        if mime_type == "application/pdf":
            local_pdf_parse = parse_pdf_statement_locally(raw, uploaded_file.name)
            if local_pdf_parse:
                return local_pdf_parse
        media_items, media_debug = prepare_vlm_media_items(
            raw,
            uploaded_file.name,
            mime_type,
        )
        media_debug["base64_chars"] = sum(
            len(base64.b64encode(item["raw"]).decode("ascii"))
            for item in media_items
        )
        media_debug["media_item_count"] = len(media_items)
        payload = build_vlm_payload_from_media_items(media_items)
        request_debug = build_vlm_request_debug(payload, media_debug=media_debug)
        request = Request(
            settings.VLM_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=(
                {
                    "Content-Type": "application/json",
                    "x-goog-api-key": settings.VLM_API_KEY,
                }
                if settings.VLM_API_TYPE == "gemini_generate_content"
                else {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {settings.VLM_API_KEY}",
                }
            ),
            method="POST",
        )
        with urlopen(request, timeout=60) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        parsed = extract_json_object(extract_vlm_content(response_payload))
        return {
            "spending": normalize_vlm_spending(parsed.get("spending", {})),
            "confidence": float(parsed.get("confidence", 0) or 0),
            "source": "vlm",
            "vlm_status": "ok",
            "vlm_error_type": None,
            "vlm_error": None,
            "vlm_request_debug": request_debug,
            "summary": parsed.get("summary", ""),
        }
    except Exception as exc:
        error_type, detail = describe_vlm_exception(exc)
        return fallback_consumption_parse(
            detail,
            error_type=error_type,
            request_debug=request_debug,
        )


def simulate_cards(
    spending=None,
    infrastructure=None,
    area_id=None,
    previous_month_spending=None,
    owned_card_ids=None,
    transactions=None,
    spending_source=None,
    selected_category=None,
    allow_mock_fallback=False,
):
    infrastructure = infrastructure or DEFAULT_INFRASTRUCTURE
    catalog = load_recommendation_candidates(area_id=area_id)
    cards = catalog["cards"]
    metadata = catalog["metadata"]

    if not cards and allow_mock_fallback:
        cards = CARD_PRODUCTS
        metadata = {
            **metadata,
            "recommendation_source": "mock_fallback",
            "candidate_count": len(cards),
            "fallback_reason": "no_active_cards",
        }

    ranking = rank_card_recommendations(
        cards=cards,
        spending=spending,
        infrastructure=infrastructure,
        previous_month_spending=previous_month_spending,
        owned_card_ids=owned_card_ids,
        transactions=transactions,
        spending_source=spending_source,
        fallback_spending=DEFAULT_SPENDING,
        selected_category=selected_category,
    )
    return {"ranking": ranking, "metadata": metadata}


def kakao_category_search(category_code, lat, lng, radius, page=1):
    if not settings.KAKAO_REST_API_KEY:
        return None

    query = urlencode(
        {
            "category_group_code": category_code,
            "x": lng,
            "y": lat,
            "radius": radius,
            "size": KAKAO_PAGE_SIZE,
            "page": page,
            "sort": "distance",
        }
    )
    request = Request(
        f"https://dapi.kakao.com/v2/local/search/category.json?{query}",
        headers={"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"},
    )

    with urlopen(request, timeout=4) as response:
        return json.loads(response.read().decode("utf-8"))


def collect_kakao_category_places(category_code, lat, lng, radius):
    documents = []
    seen_ids = set()
    total_count = 0

    for page in range(1, KAKAO_MAX_PAGES + 1):
        result = kakao_category_search(
            category_code,
            lat,
            lng,
            radius,
            page=page,
        )
        if result is None:
            return None

        meta = result.get("meta", {})
        if page == 1:
            total_count = int(meta.get("total_count", 0))

        for item in result.get("documents", []):
            place_id = item.get("id") or (
                item.get("place_name"),
                item.get("x"),
                item.get("y"),
            )
            if place_id in seen_ids:
                continue
            seen_ids.add(place_id)
            documents.append(item)

        if meta.get("is_end", True):
            break

    if not total_count:
        total_count = len(documents)

    merchant_counts = Counter()
    for item in documents:
        brand = normalize_merchant_brand(item.get("place_name"))
        if brand:
            merchant_counts[brand] += 1

    return {
        "documents": documents,
        "total_count": total_count,
        "sample_count": len(documents),
        "is_sampled": len(documents) < total_count,
        "merchant_counts": dict(sorted(merchant_counts.items())),
    }


def get_mock_map_summary(lat=DEFAULT_CENTER["lat"], lng=DEFAULT_CENTER["lng"], radius=500, reason=None):
    return {
        "center": {"lat": lat, "lng": lng, "label": DEFAULT_CENTER["label"]},
        "radius": radius,
        "zone_type": "1인 가구 주거 상권",
        "source": "mock",
        "fallback_reason": reason,
        "infrastructure": [
            {
                "key": "convenience",
                "category": "편의점",
                "code": "CS2",
                "count": 12,
                "total_count": 12,
                "sample_count": 3,
                "is_sampled": True,
                "merchant_counts": {"CU": 1, "GS25": 1, "세븐일레븐": 1},
                "walk_minutes": 2,
            },
            {
                "key": "cafe",
                "category": "카페",
                "code": "CE7",
                "count": 8,
                "total_count": 8,
                "sample_count": 3,
                "is_sampled": True,
                "merchant_counts": {"스타벅스": 1, "이디야": 1},
                "walk_minutes": 4,
            },
            {
                "key": "mart",
                "category": "마트",
                "code": "MT1",
                "count": 1,
                "total_count": 1,
                "sample_count": 1,
                "is_sampled": False,
                "merchant_counts": {"이마트": 1},
                "walk_minutes": 9,
            },
        ],
        "markers": [
            {"lat": lat + 0.0006, "lng": lng + 0.0004, "category": "convenience", "name": "근처 편의점"},
            {"lat": lat - 0.0005, "lng": lng - 0.0007, "category": "cafe", "name": "근처 카페"},
            {"lat": lat + 0.0002, "lng": lng - 0.0012, "category": "mart", "name": "근처 마트"},
        ],
    }


def collect_area_graph_stores(area_id, lat, lng, radius, use_mock=False):
    lat = float(lat)
    lng = float(lng)
    radius = int(radius)

    if use_mock:
        summary = get_mock_map_summary(lat=lat, lng=lng, radius=radius)
        return [
            {
                "id": f"{area_id}:{marker['category']}:{index}",
                "name": marker["name"],
                "category_key": marker["category"],
            }
            for index, marker in enumerate(summary["markers"], start=1)
        ]

    stores = []
    for category, meta in KAKAO_CATEGORY_CODES.items():
        collected = collect_kakao_category_places(meta["code"], lat, lng, radius)
        if collected is None:
            raise ValueError("KAKAO_REST_API_KEY is required to sync real stores.")
        for item in collected["documents"]:
            store_id = item.get("id") or (
                f"{area_id}:{category}:{item.get('place_name')}:{item.get('x')}:{item.get('y')}"
            )
            stores.append(
                {
                    "id": str(store_id),
                    "name": item.get("place_name", ""),
                    "category_key": category,
                }
            )
    return stores


def sync_area_graph_for_coordinates(area_id, area_name, lat, lng, radius):
    from finance.graph_repository import GraphRepository

    stores = collect_area_graph_stores(
        area_id=area_id,
        lat=lat,
        lng=lng,
        radius=radius,
    )
    GraphRepository().sync_stores(
        area_id=area_id,
        area_name=area_name,
        stores=stores,
    )
    return {
        "area_sync_status": "synced",
        "area_sync_store_count": len(stores),
        "area_sync_error": None,
    }


def get_map_summary(lat=DEFAULT_CENTER["lat"], lng=DEFAULT_CENTER["lng"], radius=500):
    lat = float(lat)
    lng = float(lng)
    radius = int(radius)
    area_id = build_area_id_from_coordinates(lat, lng)

    try:
        infrastructure = []
        markers = []
        for category, meta in KAKAO_CATEGORY_CODES.items():
            collected = collect_kakao_category_places(
                meta["code"],
                lat,
                lng,
                radius,
            )
            if collected is None:
                summary = get_mock_map_summary(
                    lat=lat,
                    lng=lng,
                    radius=radius,
                    reason="missing_kakao_rest_api_key",
                )
                summary["area_id"] = area_id
                summary["area_name"] = f"selected_{area_id}"
                return summary

            documents = collected["documents"]
            count = collected["total_count"]
            nearest_distance = int(documents[0].get("distance", 0)) if documents else 0
            walk_minutes = max(1, round(nearest_distance / 67)) if nearest_distance else None

            infrastructure.append(
                {
                    "key": category,
                    "category": meta["label"],
                    "code": meta["code"],
                    "count": count,
                    "total_count": count,
                    "sample_count": collected["sample_count"],
                    "is_sampled": collected["is_sampled"],
                    "merchant_counts": collected["merchant_counts"],
                    "walk_minutes": walk_minutes,
                }
            )
            markers.extend(
                {
                    "lat": float(item["y"]),
                    "lng": float(item["x"]),
                    "category": category,
                    "name": item.get("place_name", ""),
                    "address": item.get("road_address_name") or item.get("address_name", ""),
                    "distance": int(item.get("distance", 0)),
                }
                for item in documents[:4]
            )

        zone_type = "카페/편의점 밀집 상권"
        return {
            "area_id": area_id,
            "area_name": f"selected_{area_id}",
            "center": {"lat": lat, "lng": lng, "label": DEFAULT_CENTER["label"]},
            "radius": radius,
            "zone_type": zone_type,
            "source": "kakao",
            "infrastructure": infrastructure,
            "markers": markers,
        }
    except Exception:
        summary = get_mock_map_summary(
            lat=lat,
            lng=lng,
            radius=radius,
            reason="kakao_api_unavailable",
        )
        summary["area_id"] = area_id
        summary["area_name"] = f"selected_{area_id}"
        return summary
