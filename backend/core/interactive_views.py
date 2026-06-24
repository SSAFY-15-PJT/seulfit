import json
from itertools import count

from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods


DEFAULT_OWNED_CARDS = ["트래블월렛 우리카드", "신한카드 Simple Plan+"]

_post_counter = count(31)
COMMUNITY_POSTS = [
    {
        "id": index,
        "title": title,
        "author": author,
        "time": time,
        "views": views,
        "likes": likes,
        "budget": budget,
        "tab": "자유게시판",
        "open": False,
        "comments": [],
    }
    for index, (title, author, time, views, likes, budget) in enumerate(
        [
            ("역삼역 근처 맛집 추천부탁해요", "직장인", "방금", 12, 3, "200,000원"),
            ("역삼동 근처 카페 같이가기 좋은 곳 있나요?", "커피러버", "방금", 8, 1, "150,000원"),
            ("역삼동 vs 신촌 어디가 더 좋을까요?", "분석러", "15분", 2, 1, "180,000원"),
            ("이번 달 배달 할인 이벤트 모음", "혜택왕", "1시간", 31, 6, "90,000원"),
            ("강남역 점심 할인 잘 되는 카드 있나요?", "점심러", "2시간", 42, 9, "220,000원"),
            ("카페 많이 가는 사람 추천 카드 공유", "라떼좋아", "3시간", 56, 14, "170,000원"),
            ("편의점 캐시백 카드 실제 체감 후기", "편의점러", "4시간", 73, 18, "130,000원"),
            ("마트 장보기 혜택 좋은 조합 알려주세요", "장보기왕", "5시간", 35, 7, "260,000원"),
            ("역삼동 헬스장 주변 할인 정보", "운동러", "6시간", 21, 4, "110,000원"),
            ("배달비 줄이는 카드 조합 정리", "배달마스터", "7시간", 88, 23, "240,000원"),
            ("교통비 할인은 체크카드가 나을까요?", "출퇴근러", "8시간", 48, 10, "95,000원"),
            ("신용카드 신규 이벤트 모아봤어요", "이벤트헌터", "9시간", 120, 31, "300,000원"),
            ("연회비 낮은 카드 중 괜찮은 것 추천", "절약러", "10시간", 67, 15, "160,000원"),
            ("온라인 쇼핑 혜택 좋은 카드 후기", "쇼핑러", "11시간", 94, 20, "280,000원"),
            ("술집 많은 동네에서 쓸 카드 추천", "모임러", "12시간", 39, 8, "210,000원"),
            ("병원비 할인 가능한 카드 있나요?", "건강지킴", "13시간", 28, 5, "140,000원"),
            ("교육비 결제용 카드 비교 부탁", "공부중", "14시간", 33, 6, "320,000원"),
            ("주말 데이트 코스와 카드 혜택 공유", "데이트러", "15시간", 77, 17, "250,000원"),
            ("카드 혜택 월 한도 계산 어렵네요", "초보자", "16시간", 51, 11, "190,000원"),
            ("보유 카드 정리 기준 어떻게 잡나요?", "정리왕", "17시간", 63, 13, "200,000원"),
            ("강남구 편의점 밀집 지역 분석 후기", "슬세권러", "18시간", 84, 22, "155,000원"),
            ("카드 3장 조합으로 혜택 극대화하기", "조합러", "19시간", 102, 27, "360,000원"),
            ("이번 달 소비 패턴이 바뀌었어요", "변화중", "20시간", 45, 9, "175,000원"),
            ("카페/편의점 둘 다 잡는 카드 추천", "동네러", "21시간", 69, 16, "230,000원"),
            ("현금보다 카드 혜택이 큰 구간은?", "계산러", "22시간", 58, 12, "205,000원"),
            ("카드 추천 리포트 써본 후기", "사용자", "23시간", 91, 25, "185,000원"),
        ],
        start=1,
    )
]


def _payload(request):
    return json.loads(request.body.decode("utf-8") or "{}")


def _profile(user):
    if not user.is_authenticated:
        return {
            "name": "김슬픽",
            "email": "seulpick@example.com",
            "ownedCards": DEFAULT_OWNED_CARDS,
            "monthlySpend": 800000,
        }
    return {
        "id": user.id,
        "username": user.username,
        "name": user.first_name or user.username,
        "email": user.email,
        "ownedCards": DEFAULT_OWNED_CARDS,
        "monthlySpend": 800000,
    }


def _auth_required(request):
    if request.user.is_authenticated:
        return None
    return JsonResponse({"error": "로그인이 필요합니다."}, status=401)


@require_GET
def auth_status(request):
    return JsonResponse({"authenticated": request.user.is_authenticated, "profile": _profile(request.user)})


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def register(request):
    if request.method == "OPTIONS":
        return JsonResponse({})
    data = _payload(request)
    username = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""
    name = (data.get("name") or username).strip()
    email = (data.get("email") or "").strip()
    if not username or not password:
        return JsonResponse({"error": "아이디와 비밀번호를 입력해주세요."}, status=400)
    if User.objects.filter(username=username).exists():
        return JsonResponse({"error": "이미 존재하는 아이디입니다."}, status=400)
    user = User.objects.create_user(username=username, password=password, email=email, first_name=name)
    auth_login(request, user)
    return JsonResponse({"authenticated": True, "profile": _profile(user)})


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def login(request):
    if request.method == "OPTIONS":
        return JsonResponse({})
    data = _payload(request)
    username = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""
    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"error": "아이디 또는 비밀번호가 올바르지 않습니다."}, status=400)
    auth_login(request, user)
    return JsonResponse({"authenticated": True, "profile": _profile(user)})


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def logout(request):
    if request.method == "OPTIONS":
        return JsonResponse({})
    auth_logout(request)
    return JsonResponse({"authenticated": False, "profile": _profile(request.user)})


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def update_profile(request):
    if request.method == "OPTIONS":
        return JsonResponse({})
    error = _auth_required(request)
    if error:
        return error
    data = _payload(request)
    request.user.first_name = (data.get("name") or request.user.first_name or request.user.username).strip()
    request.user.email = (data.get("email") or request.user.email).strip()
    password = data.get("password") or ""
    if password:
        request.user.set_password(password)
    request.user.save()
    if password:
        auth_login(request, request.user)
    return JsonResponse({"profile": _profile(request.user)})


@csrf_exempt
@require_http_methods(["GET", "POST", "OPTIONS"])
def community_posts(request):
    if request.method == "OPTIONS":
        return JsonResponse({})
    if request.method == "GET":
        return JsonResponse({"items": COMMUNITY_POSTS})
    error = _auth_required(request)
    if error:
        return error
    data = _payload(request)
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    budget = (data.get("budget") or "0원").strip()
    tab = (data.get("tab") or "자유게시판").strip()
    if not title:
        return JsonResponse({"error": "제목을 입력해주세요."}, status=400)
    post = {
        "id": next(_post_counter),
        "title": title,
        "content": content,
        "author": request.user.first_name or request.user.username,
        "authorUsername": request.user.username,
        "time": "방금",
        "views": 0,
        "likes": 0,
        "budget": budget,
        "tab": tab,
        "open": False,
        "comments": [],
    }
    COMMUNITY_POSTS.insert(0, post)
    return JsonResponse({"post": post, "items": COMMUNITY_POSTS})


@csrf_exempt
@require_http_methods(["PUT", "DELETE", "OPTIONS"])
def community_post_detail(request, post_id):
    if request.method == "OPTIONS":
        return JsonResponse({})
    error = _auth_required(request)
    if error:
        return error
    post = next((item for item in COMMUNITY_POSTS if item["id"] == post_id), None)
    if post is None:
        return JsonResponse({"error": "게시글을 찾을 수 없습니다."}, status=404)
    user_display_name = request.user.first_name or request.user.username
    is_owner = post.get("authorUsername") == request.user.username or (
        not post.get("authorUsername") and post.get("author") == user_display_name
    )
    if not is_owner:
        return JsonResponse({"error": "본인이 작성한 게시글만 수정/삭제할 수 있습니다."}, status=403)
    if request.method == "DELETE":
        COMMUNITY_POSTS.remove(post)
        return JsonResponse({"deleted": True, "items": COMMUNITY_POSTS})

    data = _payload(request)
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    budget = (data.get("budget") or "0원").strip()
    tab = (data.get("tab") or post.get("tab") or "자유게시판").strip()
    if not title:
        return JsonResponse({"error": "제목을 입력해주세요."}, status=400)
    post.update({"title": title, "content": content, "budget": budget, "tab": tab})
    return JsonResponse({"post": post, "items": COMMUNITY_POSTS})


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def community_comment(request, post_id):
    if request.method == "OPTIONS":
        return JsonResponse({})
    error = _auth_required(request)
    if error:
        return error
    data = _payload(request)
    text = (data.get("text") or "").strip()
    if not text:
        return JsonResponse({"error": "댓글 내용을 입력해주세요."}, status=400)
    post = next((item for item in COMMUNITY_POSTS if item["id"] == post_id), None)
    if post is None:
        return JsonResponse({"error": "게시글을 찾을 수 없습니다."}, status=404)
    comment = {
        "id": len(post["comments"]) + 1,
        "author": request.user.first_name or request.user.username,
        "text": text,
        "time": "방금",
    }
    post["comments"].append(comment)
    return JsonResponse({"comment": comment, "post": post, "items": COMMUNITY_POSTS})
