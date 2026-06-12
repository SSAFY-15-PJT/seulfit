import json
from math import tanh
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


DEFAULT_SPENDING = {
    "cafe": 102000,
    "convenience": 58000,
    "food": 183000,
    "mart": 89000,
    "shopping": 44000,
}

CATEGORY_LABELS = {
    "cafe": "카페",
    "convenience": "편의점",
    "food": "외식",
    "mart": "마트",
    "shopping": "쇼핑",
}

KAKAO_CATEGORY_CODES = {
    "convenience": {"code": "CS2", "label": "편의점"},
    "cafe": {"code": "CE7", "label": "카페"},
    "mart": {"code": "MT1", "label": "마트"},
    "food": {"code": "FD6", "label": "음식점"},
}

CARD_PRODUCTS = [
    {
        "id": 1,
        "name": "신한 딥드림",
        "issuer": "신한카드",
        "focus": ["cafe", "convenience"],
        "discount_rate": 0.075,
        "max_discount_limit": 30000,
    },
    {
        "id": 2,
        "name": "현대 ZERO",
        "issuer": "현대카드",
        "focus": ["food", "cafe"],
        "discount_rate": 0.052,
        "max_discount_limit": 22000,
    },
    {
        "id": 3,
        "name": "삼성 iD ON",
        "issuer": "삼성카드",
        "focus": ["convenience", "mart"],
        "discount_rate": 0.048,
        "max_discount_limit": 18000,
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


def simulate_cards(spending=None, infrastructure=None):
    spending = spending or DEFAULT_SPENDING
    infrastructure = infrastructure or {"cafe": 8, "convenience": 12, "food": 9, "mart": 1}

    ranking = []
    for card in CARD_PRODUCTS:
        expected_discount = 0
        score_basis = 0

        for category in card["focus"]:
            amount = int(spending.get(category, 0))
            store_count = int(infrastructure.get(category, 0))
            match_weight = tanh(store_count / 2)
            expected_discount += amount * card["discount_rate"] * match_weight
            score_basis += match_weight * 50

        expected_discount = min(int(expected_discount), card["max_discount_limit"])
        ranking.append(
            {
                "id": card["id"],
                "name": card["name"],
                "issuer": card["issuer"],
                "focus": [CATEGORY_LABELS.get(item, item) for item in card["focus"]],
                "estimated_savings": expected_discount,
                "seul_score": round(min(100, score_basis + expected_discount / 1000), 1),
            }
        )

    return sorted(ranking, key=lambda item: item["seul_score"], reverse=True)


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
