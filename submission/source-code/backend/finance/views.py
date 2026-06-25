from rest_framework.response import Response
from rest_framework.views import APIView

from finance.card_catalog import serialize_card_product
from finance.models import CardProduct


class CardProductListView(APIView):
    def get(self, request):
        requested_status = request.query_params.get("status")
        queryset = CardProduct.objects.prefetch_related(
            "benefits",
            "benefit_tiers",
            "images",
        )
        if requested_status:
            queryset = queryset.filter(parse_status=requested_status)
        return Response(
            {
                "count": queryset.count(),
                "results": [serialize_card_product(card) for card in queryset],
            }
        )

