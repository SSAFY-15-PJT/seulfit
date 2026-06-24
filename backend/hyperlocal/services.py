import base64
import io
import json
import mimetypes
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
]
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
    "shopping": "shopping",
    "쇼핑": "shopping",
}


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
        "media": media_debug or {},
    }


def fallback_consumption_parse(reason=None, error_type="vlm_fallback", request_debug=None):
    return {
        "spending": DEFAULT_SPENDING,
        "confidence": 0.94,
        "source": "mock_vision_parser",
        "fallback_reason": reason,
        "vlm_status": "fallback",
        "vlm_error_type": error_type,
        "vlm_error": reason,
        "vlm_request_debug": request_debug or build_vlm_request_debug(),
    }


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


def normalize_vlm_spending(spending):
    normalized = {category: 0 for category in VLM_SPENDING_CATEGORIES}
    if not isinstance(spending, dict):
        return normalized
    for key, value in spending.items():
        canonical = VLM_CATEGORY_ALIASES.get(str(key).strip().lower())
        if not canonical:
            continue
        try:
            amount = int(float(str(value).replace(",", "").replace("원", "").strip() or 0))
        except (TypeError, ValueError):
            amount = 0
        normalized[canonical] += max(0, amount)
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
        image.thumbnail((1280, 1280))
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85, optimize=True)
        resized = buffer.getvalue()
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


def build_vlm_payload(data_url, filename, mime_type):
    prompt = (
        "이미지의 카드/가계부/소비 리포트에서 월간 카테고리별 소비금액을 추출하세요. "
        "반드시 JSON만 응답하세요. 형식: "
        '{"spending":{"cafe":0,"convenience":0,"dining":0,"delivery":0,"mart":0,"shopping":0},'
        '"confidence":0.0,"summary":"짧은 한국어 요약"}. '
        "금액은 원 단위 정수입니다. 알 수 없는 항목은 0으로 둡니다."
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


def parse_consumption_image(uploaded_file):
    if not uploaded_file:
        return fallback_consumption_parse("missing_file")
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
        raw, mime_type, media_debug = prepare_vlm_media(raw, uploaded_file.name, mime_type)
        encoded_media = base64.b64encode(raw).decode("ascii")
        media_debug["base64_chars"] = len(encoded_media)
        data_url = f"data:{mime_type};base64,{encoded_media}"
        payload = build_vlm_payload(
            data_url=data_url,
            filename=uploaded_file.name,
            mime_type=mime_type,
        )
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
