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
        "likes": 0,
        "budget": "0원",
        "tab": "자유게시판",
        "comments": [],
    },
    {
        "id": 2,
        "card": "현대 ZERO",
        "title": "이태원 경리단길 카페 추천 목록",
        "body": "직접 방문해 확인한 카페 가맹점 목록을 공유합니다.",
        "author": "이절약",
        "neighborhood": "이태원동",
        "views": 89,
        "likes": 0,
        "budget": "0원",
        "tab": "동네 정보",
        "comments": [],
    },
    {
        "id": 3,
        "title": "카페 많이 가는 사람 카드 조합 추천",
        "body": "카페와 편의점을 자주 쓰는 분들은 월 한도와 전월실적을 같이 보는 게 좋았습니다.",
        "author": "라떼좋아",
        "time": "10분 전",
        "views": 73,
        "likes": 12,
        "budget": "180,000원",
        "tab": "카드 추천",
        "comments": [],
    },
    {
        "id": 4,
        "title": "강남역 점심 결제할 때 체감 좋은 혜택",
        "body": "점심값이 많이 나가는 달에는 음식점 할인 카드가 생각보다 크게 체감됐어요.",
        "author": "점심러",
        "time": "25분 전",
        "views": 48,
        "likes": 8,
        "budget": "220,000원",
        "tab": "사용 후기",
        "comments": [],
    },
    {
        "id": 5,
        "title": "편의점 캐시백 카드 실제 후기",
        "body": "GS25와 CU를 번갈아 쓰는 편이라 가맹점 범위가 넓은 카드가 더 편했습니다.",
        "author": "편의점러",
        "time": "45분 전",
        "views": 91,
        "likes": 16,
        "budget": "130,000원",
        "tab": "사용 후기",
        "comments": [],
    },
    {
        "id": 6,
        "title": "마트 장보기 혜택 좋은 카드 비교 부탁",
        "body": "이마트, 롯데마트, 동네마트를 섞어 쓰는데 어떤 기준으로 골라야 할까요?",
        "author": "장보기왕",
        "time": "1시간 전",
        "views": 52,
        "likes": 7,
        "budget": "260,000원",
        "tab": "질문&답변",
        "comments": [],
    },
    {
        "id": 7,
        "title": "배달비 줄이는 카드 조합 정리",
        "body": "배달앱 할인은 월 한도와 현장결제 제외 조건을 꼭 확인해야 했습니다.",
        "author": "배달마스터",
        "time": "2시간 전",
        "views": 120,
        "likes": 24,
        "budget": "240,000원",
        "tab": "카드 추천",
        "comments": [],
    },
    {
        "id": 8,
        "title": "교통비 할인은 체크카드가 나을까요?",
        "body": "대중교통 위주로 쓰는 사회초년생이라 연회비 없는 카드도 보고 있습니다.",
        "author": "출퇴근러",
        "time": "3시간 전",
        "views": 38,
        "likes": 5,
        "budget": "95,000원",
        "tab": "질문&답변",
        "comments": [],
    },
    {
        "id": 9,
        "title": "신용카드 신규 이벤트 모아봤어요",
        "body": "이벤트 금액만 보지 말고 실적 인정 제외 항목도 같이 확인하는 게 좋습니다.",
        "author": "이벤트헌터",
        "time": "4시간 전",
        "views": 156,
        "likes": 31,
        "budget": "300,000원",
        "tab": "이벤트",
        "comments": [],
    },
    {
        "id": 10,
        "title": "연회비 낮은 카드 중 괜찮은 것 추천",
        "body": "월 소비가 크지 않아서 연회비 없는 체크카드와 저연회비 신용카드를 비교 중입니다.",
        "author": "절약러",
        "time": "5시간 전",
        "views": 80,
        "likes": 13,
        "budget": "160,000원",
        "tab": "질문&답변",
        "comments": [],
    },
    {
        "id": 11,
        "title": "온라인 쇼핑 혜택 좋은 카드 후기",
        "body": "쿠팡, 무신사, 네이버페이를 같이 쓰면 쇼핑 카테고리 카드가 꽤 유리했습니다.",
        "author": "쇼핑러",
        "time": "6시간 전",
        "views": 103,
        "likes": 18,
        "budget": "280,000원",
        "tab": "사용 후기",
        "comments": [],
    },
    {
        "id": 12,
        "title": "술집 많은 동네에서 쓸 카드 추천",
        "body": "모임이 잦은 달에는 음식점/외식 혜택과 택시 혜택을 같이 보고 있어요.",
        "author": "모임러",
        "time": "7시간 전",
        "views": 44,
        "likes": 9,
        "budget": "210,000원",
        "tab": "카드 추천",
        "comments": [],
    },
    {
        "id": 13,
        "title": "병원비 할인 가능한 카드 있나요?",
        "body": "의료비는 할인 제외가 많은 것 같아서 실제 적용되는 카드가 궁금합니다.",
        "author": "건강지킴",
        "time": "8시간 전",
        "views": 36,
        "likes": 4,
        "budget": "140,000원",
        "tab": "질문&답변",
        "comments": [],
    },
    {
        "id": 14,
        "title": "교육비 결제용 카드 비교 부탁",
        "body": "학원비와 온라인 강의 결제가 실적으로 잡히는지 확인하고 싶습니다.",
        "author": "공부중",
        "time": "9시간 전",
        "views": 41,
        "likes": 6,
        "budget": "320,000원",
        "tab": "질문&답변",
        "comments": [],
    },
    {
        "id": 15,
        "title": "주말 데이트 코스와 카드 혜택 공유",
        "body": "영화, 카페, 음식점을 한 번에 묶으면 혜택 조합이 꽤 괜찮았습니다.",
        "author": "데이트러",
        "time": "10시간 전",
        "views": 77,
        "likes": 17,
        "budget": "250,000원",
        "tab": "동네 정보",
        "comments": [],
    },
    {
        "id": 16,
        "title": "카드 혜택 월 한도 계산 어렵네요",
        "body": "할인율보다 월 한도가 실제 혜택에 더 큰 영향을 주는 경우가 많았습니다.",
        "author": "초보자",
        "time": "11시간 전",
        "views": 64,
        "likes": 10,
        "budget": "190,000원",
        "tab": "자유게시판",
        "comments": [],
    },
    {
        "id": 17,
        "title": "보유 카드 정리 기준 어떻게 잡나요?",
        "body": "겹치는 혜택 카드는 줄이고 소비 카테고리별로 하나씩 남기는 게 좋을까요?",
        "author": "정리왕",
        "time": "12시간 전",
        "views": 72,
        "likes": 14,
        "budget": "200,000원",
        "tab": "질문&답변",
        "comments": [],
    },
    {
        "id": 18,
        "title": "강남구 편의점 밀집 지역 분석 후기",
        "body": "지도 반경을 좁히니까 실제 자주 가는 편의점이 더 잘 반영되는 느낌이었습니다.",
        "author": "슬세권러",
        "time": "13시간 전",
        "views": 94,
        "likes": 21,
        "budget": "155,000원",
        "tab": "사용 후기",
        "comments": [],
    },
    {
        "id": 19,
        "title": "카드 3장 조합으로 혜택 극대화하기",
        "body": "카페, 배달, 마트를 나눠 쓰니 월 혜택이 더 안정적으로 나왔습니다.",
        "author": "조합러",
        "time": "14시간 전",
        "views": 132,
        "likes": 27,
        "budget": "360,000원",
        "tab": "카드 추천",
        "comments": [],
    },
    {
        "id": 20,
        "title": "이번 달 소비 패턴이 바뀌었어요",
        "body": "외식이 줄고 마트 소비가 늘어서 추천 카드도 바뀌는지 테스트해봤습니다.",
        "author": "변화중",
        "time": "15시간 전",
        "views": 55,
        "likes": 8,
        "budget": "175,000원",
        "tab": "자유게시판",
        "comments": [],
    },
    {
        "id": 21,
        "title": "카페/편의점 둘 다 잡는 카드 추천",
        "body": "소액 결제가 많으면 건별 한도보다 월 사용 횟수 조건이 더 중요했습니다.",
        "author": "동네러",
        "time": "16시간 전",
        "views": 88,
        "likes": 19,
        "budget": "230,000원",
        "tab": "카드 추천",
        "comments": [],
    },
    {
        "id": 22,
        "title": "현금보다 카드 혜택이 큰 구간은?",
        "body": "전월실적을 채울 수 있는 소비 규모라면 카드 혜택이 더 유리한 구간이 있네요.",
        "author": "계산러",
        "time": "17시간 전",
        "views": 67,
        "likes": 11,
        "budget": "205,000원",
        "tab": "자유게시판",
        "comments": [],
    },
    {
        "id": 23,
        "title": "카드 추천 리포트 써본 후기",
        "body": "소비 리포트 업로드 후 카테고리별 추천이 자동으로 바뀌는 점이 편했습니다.",
        "author": "사용자",
        "time": "18시간 전",
        "views": 118,
        "likes": 25,
        "budget": "185,000원",
        "tab": "사용 후기",
        "comments": [],
    },
    {
        "id": 24,
        "title": "잠실 근처 마트 혜택 정보 공유",
        "body": "잠실 생활권은 마트와 외식 비중이 커서 추천 결과가 강남역과 다르게 나왔습니다.",
        "author": "잠실러",
        "time": "19시간 전",
        "views": 61,
        "likes": 9,
        "budget": "270,000원",
        "tab": "동네 정보",
        "comments": [],
    },
    {
        "id": 25,
        "title": "홍대 카페거리 카드 혜택 체감",
        "body": "카페 가맹점이 많아서 카페형 카드의 Graph 후보 점수가 높게 나왔습니다.",
        "author": "홍대러",
        "time": "20시간 전",
        "views": 74,
        "likes": 15,
        "budget": "165,000원",
        "tab": "동네 정보",
        "comments": [],
    },
    {
        "id": 26,
        "title": "이번 주 발급 이벤트 체크리스트",
        "body": "캐시백 조건, 자동이체 조건, 실적 제외 조건을 같이 확인해야 합니다.",
        "author": "체크리스트",
        "time": "21시간 전",
        "views": 143,
        "likes": 30,
        "budget": "0원",
        "tab": "이벤트",
        "comments": [],
    },
    {
        "id": 27,
        "title": "체크카드만으로 충분한 소비 패턴",
        "body": "교통, 편의점, 카페 위주라면 연회비 없는 카드 조합도 괜찮았습니다.",
        "author": "체크러",
        "time": "22시간 전",
        "views": 81,
        "likes": 12,
        "budget": "120,000원",
        "tab": "사용 후기",
        "comments": [],
    },
    {
        "id": 28,
        "title": "슬세권 분석 반경은 몇 미터가 좋나요?",
        "body": "300m는 너무 좁고 800m는 넓어서 저는 500m가 가장 현실적이었습니다.",
        "author": "반경고민",
        "time": "23시간 전",
        "views": 69,
        "likes": 10,
        "budget": "0원",
        "tab": "질문&답변",
        "comments": [],
    },
    {
        "id": 29,
        "title": "카드 혜택 조건 읽는 법 정리",
        "body": "전월실적, 월 한도, 건별 한도, 제외 가맹점을 순서대로 보면 실수 확률이 줄었습니다.",
        "author": "약관러",
        "time": "1일 전",
        "views": 96,
        "likes": 22,
        "budget": "0원",
        "tab": "자유게시판",
        "comments": [],
    },
    {
        "id": 30,
        "title": "다음 달 소비 리포트 업로드 예정",
        "body": "PDF 명세서도 잘 분석되는지 확인해보고 결과 공유하겠습니다.",
        "author": "리포트러",
        "time": "1일 전",
        "views": 58,
        "likes": 7,
        "budget": "0원",
        "tab": "자유게시판",
        "comments": [],
    },
]


def _normalize_post(item):
    return {
        "id": item.get("id"),
        "title": item.get("title", ""),
        "content": item.get("content") or item.get("body", ""),
        "body": item.get("body") or item.get("content", ""),
        "author": item.get("author", "익명"),
        "authorUsername": item.get("authorUsername", ""),
        "time": item.get("time", "방금"),
        "views": item.get("views", 0),
        "likes": item.get("likes", 0),
        "budget": item.get("budget", "0원"),
        "tab": item.get("tab", "자유게시판"),
        "open": item.get("open", False),
        "comments": item.get("comments", []),
    }


def _items():
    return [_normalize_post(item) for item in POSTS]


def _find_post(post_id):
    return next((item for item in POSTS if item["id"] == post_id), None)


def _find_comment(post, comment_id):
    comments = post.setdefault("comments", [])
    return next((item for item in comments if item["id"] == comment_id), None)


class PostListCreateView(APIView):
    def get(self, request):
        return Response({"items": _items(), "results": _items()})

    def post(self, request):
        item = {
            "id": max([post["id"] for post in POSTS] or [0]) + 1,
            "author": getattr(request.user, "first_name", "") or getattr(request.user, "username", "") or "익명",
            "time": "방금",
            "views": 0,
            "likes": 0,
            "comments": [],
            **request.data,
        }
        POSTS.insert(0, item)
        return Response({"post": _normalize_post(item), "items": _items()}, status=201)


class PostDetailView(APIView):
    def put(self, request, post_id):
        post = _find_post(post_id)
        if post is None:
            return Response({"error": "게시글을 찾을 수 없습니다."}, status=404)
        post.update(request.data)
        return Response({"post": _normalize_post(post), "items": _items()})

    def delete(self, request, post_id):
        post = _find_post(post_id)
        if post is None:
            return Response({"error": "게시글을 찾을 수 없습니다."}, status=404)
        POSTS.remove(post)
        return Response({"deleted": True, "items": _items()})


class CommentCreateView(APIView):
    def post(self, request, post_id):
        post = _find_post(post_id)
        if post is None:
            return Response({"error": "게시글을 찾을 수 없습니다."}, status=404)
        text = (request.data.get("text") or "").strip()
        if not text:
            return Response({"error": "댓글 내용을 입력해주세요."}, status=400)
        comments = post.setdefault("comments", [])
        comment = {
            "id": len(comments) + 1,
            "author": getattr(request.user, "first_name", "") or getattr(request.user, "username", "") or "익명",
            "authorUsername": getattr(request.user, "username", "") or "",
            "text": text,
            "time": "방금",
        }
        comments.append(comment)
        return Response({"comment": comment, "post": _normalize_post(post), "items": _items()})


class CommentDetailView(APIView):
    def put(self, request, post_id, comment_id):
        post = _find_post(post_id)
        if post is None:
            return Response({"error": "게시글을 찾을 수 없습니다."}, status=404)
        comment = _find_comment(post, comment_id)
        if comment is None:
            return Response({"error": "댓글을 찾을 수 없습니다."}, status=404)
        text = (request.data.get("text") or "").strip()
        if not text:
            return Response({"error": "댓글 내용을 입력해주세요."}, status=400)
        comment["text"] = text
        return Response({"comment": comment, "post": _normalize_post(post), "items": _items()})

    def delete(self, request, post_id, comment_id):
        post = _find_post(post_id)
        if post is None:
            return Response({"error": "게시글을 찾을 수 없습니다."}, status=404)
        comment = _find_comment(post, comment_id)
        if comment is None:
            return Response({"error": "댓글을 찾을 수 없습니다."}, status=404)
        post.setdefault("comments", []).remove(comment)
        return Response({"deleted": True, "post": _normalize_post(post), "items": _items()})


class PostLikeView(APIView):
    def post(self, request, post_id):
        post = _find_post(post_id)
        if post is None:
            return Response({"error": "게시글을 찾을 수 없습니다."}, status=404)
        post["likes"] = int(post.get("likes") or 0) + 1
        return Response({"post": _normalize_post(post), "items": _items()})

