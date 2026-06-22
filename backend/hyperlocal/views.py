from rest_framework.response import Response
from rest_framework.views import APIView

from .services import get_map_summary, parse_consumption_image, simulate_cards


CATEGORY_KEY_ALIASES = {
    "카페": "cafe",
    "편의점": "convenience",
    "외식": "dining",
    "음식점": "dining",
    "배달": "delivery",
    "마트": "mart",
    "쇼핑": "shopping",
    "기타": "etc",
    "CE7": "cafe",
    "CS2": "convenience",
    "FD6": "dining",
    "MT1": "mart",
}


def normalize_infrastructure(infrastructure):
    if isinstance(infrastructure, dict):
        normalized = {}
        for key, value in infrastructure.items():
            canonical_key = CATEGORY_KEY_ALIASES.get(str(key), str(key))
            normalized[canonical_key] = value
        return normalized
    if isinstance(infrastructure, list):
        normalized = {}
        for item in infrastructure:
            if not isinstance(item, dict):
                continue
            category = item.get("category") or item.get("code")
            if not category:
                continue
            canonical_key = CATEGORY_KEY_ALIASES.get(str(category), str(category))
            normalized[canonical_key] = item.get("count", item.get("store_count", 0))
        return normalized
    return {}


class ParseImageView(APIView):
    def post(self, request):
        uploaded_file = request.FILES.get("image")
        parsed = parse_consumption_image(uploaded_file)
        return Response(parsed)


class SimulateView(APIView):
    def post(self, request):
        spending = request.data.get("spending")
        infrastructure = normalize_infrastructure(request.data.get("infrastructure"))
        previous_month_spending = request.data.get("previous_month_spending", 0)
        owned_card_ids = request.data.get("owned_card_ids", [])
        transactions = request.data.get("transactions")
        spending_source = request.data.get("spending_source")
        allow_mock_fallback = request.data.get("allow_mock_fallback", False) is True
        simulation = simulate_cards(
            spending=spending,
            infrastructure=infrastructure,
            previous_month_spending=previous_month_spending,
            owned_card_ids=owned_card_ids,
            transactions=transactions,
            spending_source=spending_source,
            allow_mock_fallback=allow_mock_fallback,
        )
        ranking = simulation["ranking"]
        spending_profile = ranking[0]["spending_profile"] if ranking else None
        return Response(
            {
                "spending": spending,
                "spending_profile": spending_profile,
                "previous_month_spending": previous_month_spending,
                "owned_card_ids": owned_card_ids,
                "card_ranking_list": ranking,
                "best_card": ranking[0] if ranking else None,
                **simulation["metadata"],
            }
        )


class MapSummaryView(APIView):
    def get(self, request):
        lat = request.query_params.get("lat", 37.4979)
        lng = request.query_params.get("lng", 127.0276)
        radius = request.query_params.get("radius", 500)
        return Response(get_map_summary(lat=lat, lng=lng, radius=radius))


class WeatherCurationView(APIView):
    def get(self, request):
        return Response(
            {
                "temperature_celsius": 32.5,
                "condition": "맑음",
                "message": "강남역 주변 카페 밀도가 높아요. 오늘은 카페 할인 강점이 있는 카드를 우선 추천합니다.",
            }
        )
