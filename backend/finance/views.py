from rest_framework.response import Response
from rest_framework.views import APIView

from hyperlocal.services import CARD_PRODUCTS


class CardProductListView(APIView):
    def get(self, request):
        return Response({"results": CARD_PRODUCTS})

