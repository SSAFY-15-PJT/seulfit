from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response


EXAMPLE_VIDEOS = [
    {
        "id": 1,
        "title": "[예제] 2026 혜택 좋은 신용카드 TOP 5",
        "channel": "카드토크",
        "views": "12만",
        "age": "2일 전",
        "duration": "8:21",
        "tags": ["카드추천", "혜택비교"],
    },
    {
        "id": 2,
        "title": "[예제] 사회초년생 카드 추천 정리",
        "channel": "머니레인",
        "views": "6.4만",
        "age": "5일 전",
        "duration": "10:31",
        "tags": ["체크카드", "초년생"],
    },
]


@api_view(["GET"])
def config(request):
    return Response(
        {
            "kakaoMapApiKey": getattr(settings, "KAKAO_JAVASCRIPT_KEY", ""),
            "apis": {
                "kakaoMap": bool(getattr(settings, "KAKAO_REST_API_KEY", "")),
                "youtube": False,
            },
        }
    )


@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "service": "SeulPick"})


@api_view(["GET"])
def overview(request):
    return Response(
        {
            "area": "서울 강남구 역삼동",
            "linkedSpend": 800000,
            "recommendedCards": 0,
            "seulScore": 0,
        }
    )


@api_view(["GET"])
def places(request):
    category = request.query_params.get("category", "전체")
    items = [
        {"id": 1, "name": "브루잉 사인점", "category": "카페", "distance": 120},
        {"id": 2, "name": "세븐역삼점", "category": "편의점", "distance": 180},
        {"id": 3, "name": "그린마트 역삼", "category": "마트", "distance": 260},
    ]
    if category != "전체":
        items = [item for item in items if item["category"] == category]
    return Response(
        {
            "items": items,
            "categories": ["전체", "편의점", "카페", "마트", "음식점", "기타"],
        }
    )


@api_view(["GET"])
def recommendations(request):
    return Response({"items": [], "ownedCards": []})


@api_view(["GET"])
def videos(request):
    return Response(
        {
            "source": "example",
            "categories": ["전체", "카드 추천", "혜택 비교", "사용 후기", "비교 분석"],
            "popularKeywords": ["카드 추천", "혜택 비교", "연회비", "카드 정리"],
            "channels": [{"name": "카드토크"}, {"name": "머니레인"}],
            "items": EXAMPLE_VIDEOS,
        }
    )


@api_view(["GET"])
def community(request):
    return Response({"items": [], "tabs": ["전체", "자유게시판", "질문&답변", "동네 정보", "이벤트"]})


@api_view(["POST"])
def ai_analyze(request):
    return Response(
        {
            "source": "compat",
            "summary": "이미지 소비패턴 분석은 /api/v1/hyperlocal/parse-image/ 또는 VLM 저장 흐름을 사용하세요.",
            "rows": [],
        }
    )
