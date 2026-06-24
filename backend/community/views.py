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
        POSTS.append(item)
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
            "text": text,
            "time": "방금",
        }
        comments.append(comment)
        return Response({"comment": comment, "post": _normalize_post(post), "items": _items()})

