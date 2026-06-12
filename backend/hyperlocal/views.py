from rest_framework.response import Response
from rest_framework.views import APIView

from .services import DEFAULT_SPENDING, get_map_summary, parse_consumption_image, simulate_cards


class ParseImageView(APIView):
    def post(self, request):
        uploaded_file = request.FILES.get("image")
        parsed = parse_consumption_image(uploaded_file)
        return Response(parsed)


class SimulateView(APIView):
    def post(self, request):
        spending = request.data.get("spending") or DEFAULT_SPENDING
        infrastructure = request.data.get("infrastructure")
        ranking = simulate_cards(spending=spending, infrastructure=infrastructure)
        return Response(
            {
                "spending": spending,
                "card_ranking_list": ranking,
                "best_card": ranking[0] if ranking else None,
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
