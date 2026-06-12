from rest_framework.response import Response
from rest_framework.views import APIView


class ProfileView(APIView):
    def get(self, request):
        return Response(
            {
                "username": "seulpick-demo",
                "nickname": "김커피",
                "home_address": "서울 강남구 역삼동",
                "favorite_cards": ["신한 딥드림", "현대 ZERO"],
                "uploaded_report": None,
            }
        )

