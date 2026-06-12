from rest_framework.response import Response
from rest_framework.views import APIView


POSTS = [
    {
        "id": 1,
        "card": "신한 딥드림",
        "title": "강남역 GS25 가맹점 분류 제보",
        "body": "지도 분류가 편의점으로 반영되면 할인 추정치가 더 정확해질 것 같아요.",
        "author": "김커피",
        "neighborhood": "강남역",
        "views": 142,
    },
    {
        "id": 2,
        "card": "현대 ZERO",
        "title": "이태원 경리단길 카페 추천 목록",
        "body": "직접 방문해 확인한 카페 가맹점 목록을 공유합니다.",
        "author": "이절약",
        "neighborhood": "이태원동",
        "views": 89,
    },
]


class PostListCreateView(APIView):
    def get(self, request):
        return Response({"results": POSTS})

    def post(self, request):
        item = {"id": len(POSTS) + 1, **request.data}
        POSTS.append(item)
        return Response(item, status=201)

