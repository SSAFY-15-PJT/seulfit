import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

from finance.card_catalog import load_recommendation_candidates
from finance.recommendation import (
    CATEGORY_LABELS,
    DEFAULT_COHORT_SPENDING,
    DEFAULT_INFRASTRUCTURE,
    rank_card_recommendations,
)


DEFAULT_SPENDING = DEFAULT_COHORT_SPENDING

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


def parse_consumption_image(_uploaded_file):
    """Replace this with OpenAI/Gemini vision parsing in production."""
    return {
        "spending": DEFAULT_SPENDING,
        "confidence": 0.94,
        "source": "mock_vision_parser",
    }


def simulate_cards(
    spending=None,
    infrastructure=None,
    previous_month_spending=0,
    owned_card_ids=None,
    transactions=None,
    spending_source=None,
    allow_mock_fallback=False,
):
    infrastructure = infrastructure or DEFAULT_INFRASTRUCTURE
    catalog = load_recommendation_candidates()
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
    )
    return {"ranking": ranking, "metadata": metadata}


def kakao_category_search(category_code, lat, lng, radius):
    if not settings.KAKAO_REST_API_KEY:
        return None

    query = urlencode(
        {
            "category_group_code": category_code,
            "x": lng,
            "y": lat,
            "radius": radius,
            "size": 15,
            "sort": "distance",
        }
    )
    request = Request(
        f"https://dapi.kakao.com/v2/local/search/category.json?{query}",
        headers={"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"},
    )

    with urlopen(request, timeout=4) as response:
        return json.loads(response.read().decode("utf-8"))


def get_mock_map_summary(lat=DEFAULT_CENTER["lat"], lng=DEFAULT_CENTER["lng"], radius=500, reason=None):
    return {
        "center": {"lat": lat, "lng": lng, "label": DEFAULT_CENTER["label"]},
        "radius": radius,
        "zone_type": "1인 가구 주거 상권",
        "source": "mock",
        "fallback_reason": reason,
        "infrastructure": [
            {"category": "편의점", "code": "CS2", "count": 12, "walk_minutes": 2},
            {"category": "카페", "code": "CE7", "count": 8, "walk_minutes": 4},
            {"category": "마트", "code": "MT1", "count": 1, "walk_minutes": 9},
        ],
        "markers": [
            {"lat": lat + 0.0006, "lng": lng + 0.0004, "category": "convenience", "name": "근처 편의점"},
            {"lat": lat - 0.0005, "lng": lng - 0.0007, "category": "cafe", "name": "근처 카페"},
            {"lat": lat + 0.0002, "lng": lng - 0.0012, "category": "mart", "name": "근처 마트"},
        ],
    }


def get_map_summary(lat=DEFAULT_CENTER["lat"], lng=DEFAULT_CENTER["lng"], radius=500):
    lat = float(lat)
    lng = float(lng)
    radius = int(radius)

    try:
        infrastructure = []
        markers = []
        for category, meta in KAKAO_CATEGORY_CODES.items():
            result = kakao_category_search(meta["code"], lat, lng, radius)
            if result is None:
                return get_mock_map_summary(lat=lat, lng=lng, radius=radius, reason="missing_kakao_rest_api_key")

            documents = result.get("documents", [])
            count = int(result.get("meta", {}).get("total_count", len(documents)))
            nearest_distance = int(documents[0].get("distance", 0)) if documents else 0
            walk_minutes = max(1, round(nearest_distance / 67)) if nearest_distance else None

            infrastructure.append(
                {
                    "category": meta["label"],
                    "code": meta["code"],
                    "count": count,
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
            "center": {"lat": lat, "lng": lng, "label": DEFAULT_CENTER["label"]},
            "radius": radius,
            "zone_type": zone_type,
            "source": "kakao",
            "infrastructure": infrastructure,
            "markers": markers,
        }
    except Exception:
        return get_mock_map_summary(lat=lat, lng=lng, radius=radius, reason="kakao_api_unavailable")
