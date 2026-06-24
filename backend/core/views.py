import base64
import json
import mimetypes
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods


CARDS = [
    {"id": "woori-travel", "name": "트래블월렛 우리카드", "issuer": "우리카드", "match": 92, "saving": 32400, "owned": True, "tags": ["카페", "편의점", "마트"], "benefits": ["카페 50% 할인", "편의점 10% 할인", "마트 5% 할인"]},
    {"id": "toss-check", "name": "토스뱅크 체크카드", "issuer": "토스뱅크", "match": 88, "saving": 21300, "owned": False, "tags": ["편의점", "배달"], "benefits": ["편의점 캐시백 3%", "카페 캐시백 2%", "연회비 없음"]},
    {"id": "simple-plan", "name": "신한카드 Simple Plan+", "issuer": "신한카드", "match": 78, "saving": 19600, "owned": True, "tags": ["음식점", "카페"], "benefits": ["음식점 10% 할인", "카페 5% 할인", "생활 업종 적립"]},
]

PROFILE = {
    "name": "김슬픽",
    "email": "seulpick@example.com",
    "ownedCards": ["트래블월렛 우리카드", "신한카드 Simple Plan+"],
    "monthlySpend": 800000,
}

YOUTUBE_CATEGORIES = ["전체", "카드 추천", "혜택 비교", "사용 후기", "비교 분석"]
YOUTUBE_CATEGORY_QUERIES = {
    "전체": "신용카드 추천 혜택 비교",
    "카드 추천": "신용카드 추천",
    "혜택 비교": "카드 혜택 비교",
    "사용 후기": "카드 사용 후기",
    "비교 분석": "카드 혜택 비교 분석",
}
YOUTUBE_POPULAR_KEYWORDS = ["카드 추천", "혜택 비교", "연회비", "카드 정리", "소비 패턴"]
SPEND_CATEGORIES = ["카페", "편의점", "마트/슈퍼", "음식점/배달", "의류/소품", "교통", "기타"]


def _contains(value, query):
    return query.lower() in value.lower()


def _youtube_get(path, params):
    url = f"https://www.googleapis.com/youtube/v3/{path}?{urlencode(params)}"
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _format_view_count(value):
    count = int(value or 0)
    if count >= 10000:
        return f"{round(count / 10000, 1)}만"
    return f"{count:,}"


def _parse_duration(iso_duration):
    value = iso_duration.removeprefix("PT")
    hours = minutes = seconds = 0
    number = ""
    for char in value:
        if char.isdigit():
            number += char
            continue
        if char == "H":
            hours = int(number or 0)
        elif char == "M":
            minutes = int(number or 0)
        elif char == "S":
            seconds = int(number or 0)
        number = ""
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _fallback_videos(query, category):
    videos = [
        {"id": 1, "isExample": True, "title": "[예제] 2026 혜택 좋은 신용카드 TOP 5", "channel": "카드테크랩", "views": "12만", "age": "2일 전", "duration": "8:21", "category": "카드 추천", "tags": ["카드추천", "혜택비교"]},
        {"id": 2, "isExample": True, "title": "[예제] 사회초년생 카드 추천 정리", "channel": "머니레이더", "views": "6.4만", "age": "5일 전", "duration": "10:31", "category": "카드 추천", "tags": ["체크카드", "초년생"]},
        {"id": 3, "isExample": True, "title": "[예제] 월 10만원 아끼는 카드 사용법", "channel": "절약하는시그마", "views": "5.7만", "age": "1주 전", "duration": "7:12", "category": "사용 후기", "tags": ["리뷰", "카드테크"]},
        {"id": 4, "isExample": True, "title": "[예제] 역삼동 소비 분석으로 생활비 줄이기", "channel": "SeulPick 연구소", "views": "9.1만", "age": "3일 전", "duration": "9:01", "category": "비교 분석", "tags": ["상권분석", "카드혜택"]},
    ]
    if category != "전체":
        videos = [video for video in videos if video["category"] == category]
    if query:
        videos = [video for video in videos if _contains(video["title"], query) or _contains(video["channel"], query)]
    return videos


def _youtube_search(query, category):
    if not settings.YOUTUBE_API_KEY:
        return None
    search_query = query or YOUTUBE_CATEGORY_QUERIES.get(category, YOUTUBE_CATEGORY_QUERIES["전체"])
    search_data = _youtube_get(
        "search",
        {
            "key": settings.YOUTUBE_API_KEY,
            "part": "snippet",
            "type": "video",
            "maxResults": 8,
            "order": "relevance",
            "regionCode": "KR",
            "q": search_query,
        },
    )
    items = search_data.get("items", [])
    video_ids = [item["id"]["videoId"] for item in items if item.get("id", {}).get("videoId")]
    if not video_ids:
        return []
    detail_data = _youtube_get(
        "videos",
        {"key": settings.YOUTUBE_API_KEY, "part": "contentDetails,statistics,snippet", "id": ",".join(video_ids)},
    )
    details_by_id = {item["id"]: item for item in detail_data.get("items", [])}
    results = []
    for index, item in enumerate(items, start=1):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        details = details_by_id.get(video_id, {})
        results.append(
            {
                "id": video_id or index,
                "isExample": False,
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "views": _format_view_count(details.get("statistics", {}).get("viewCount")),
                "age": snippet.get("publishedAt", "")[:10],
                "duration": _parse_duration(details.get("contentDetails", {}).get("duration", "PT0M0S")),
                "category": category,
                "tags": [category.replace(" ", ""), "YouTube"],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
            }
        )
    return results


@require_GET
def config(request):
    return JsonResponse(
        {
            "kakaoMapApiKey": settings.KAKAOMAP_API_KEY,
            "apis": {
                "kakaoMap": bool(settings.KAKAOMAP_API_KEY),
                "youtube": bool(settings.YOUTUBE_API_KEY),
            },
        }
    )


@require_GET
def health(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "SeulPick",
            "apis": {
                "gms": bool(settings.GMS_KEY and settings.VLM_API_URL),
                "vlm_model": settings.VLM_MODEL,
                "youtube": bool(settings.YOUTUBE_API_KEY),
                "kakaoMap": bool(settings.KAKAOMAP_API_KEY),
            },
        }
    )


@require_GET
def overview(request):
    return JsonResponse({"area": "서울 강남구 역삼동", "linkedSpend": 800000, "recommendedCards": 3, "seulScore": 69.8})


@require_GET
def places(request):
    category = request.GET.get("category", "전체")
    places_data = [
        {"id": 1, "name": "브루잉 사인점", "category": "카페", "distance": 120},
        {"id": 2, "name": "세븐역삼점", "category": "편의점", "distance": 180},
        {"id": 3, "name": "그린마트 역삼", "category": "마트", "distance": 260},
    ]
    if category != "전체":
        places_data = [place for place in places_data if place["category"] == category]
    return JsonResponse({"items": places_data, "categories": ["전체", "편의점", "카페", "마트", "음식점", "의류/소품", "병원", "교육", "기타"]})


@require_GET
def recommendations(request):
    spend = int(request.GET.get("spend", PROFILE["monthlySpend"]))
    multiplier = max(spend / PROFILE["monthlySpend"], 0.5)
    return JsonResponse({"items": [{**card, "saving": int(card["saving"] * multiplier)} for card in CARDS], "ownedCards": PROFILE["ownedCards"]})


@require_GET
def videos(request):
    query = request.GET.get("query", "").strip()
    category = request.GET.get("category", "전체")
    if category not in YOUTUBE_CATEGORIES:
        category = "전체"
    source = "youtube"
    error = ""
    try:
        data = _youtube_search(query, category)
        if data is None:
            source = "example"
            data = _fallback_videos(query, category)
    except Exception as exc:
        source = "example"
        error = str(exc)
        data = _fallback_videos(query, category)
    return JsonResponse(
        {
            "items": data,
            "categories": YOUTUBE_CATEGORIES,
            "channels": [{"name": "짠돌이TV"}, {"name": "재테크 연구소"}, {"name": "카드의 정석"}, {"name": "혜택 연구소"}],
            "popularKeywords": YOUTUBE_POPULAR_KEYWORDS,
            "source": source,
            "error": error,
        }
    )


@require_GET
def community(request):
    return JsonResponse({"items": [], "tabs": ["전체", "자유게시판", "질문답변", "동네 정보", "이벤트"]})


@require_GET
def profile(request):
    return JsonResponse(PROFILE)


def _extract_json_object(text):
    if isinstance(text, dict):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("VLM response did not include JSON")
    return json.loads(text[start : end + 1])


def _normalize_spend_rows(rows):
    by_name = {}
    for row in rows or []:
        name = str(row.get("name") or row.get("category") or "").strip()
        amount = row.get("amount", 0)
        try:
            amount = int(float(str(amount).replace(",", "").replace("원", "").strip() or 0))
        except ValueError:
            amount = 0
        if name == "마트":
            name = "마트/슈퍼"
        if name == "음식점":
            name = "음식점/배달"
        if name in SPEND_CATEGORIES:
            by_name[name] = by_name.get(name, 0) + max(0, amount)
    total = sum(by_name.values()) or 1
    return [
        {"name": name, "amount": by_name.get(name, 0), "ratio": round(by_name.get(name, 0) / total * 100)}
        for name in SPEND_CATEGORIES
    ]


def _fallback_spend_analysis(filename="업로드 파일"):
    rows = [
        {"name": "카페", "amount": 125000},
        {"name": "편의점", "amount": 82000},
        {"name": "마트/슈퍼", "amount": 155000},
        {"name": "음식점/배달", "amount": 202000},
        {"name": "의류/소품", "amount": 135000},
        {"name": "교통", "amount": 102000},
        {"name": "기타", "amount": 25000},
    ]
    return {
        "source": "fallback",
        "summary": f"{filename} 분석 예시를 카테고리별 소비액으로 정리했습니다.",
        "rows": _normalize_spend_rows(rows),
    }


def _call_vlm_for_spend(uploaded_file):
    if not settings.GMS_KEY or not settings.VLM_API_URL or not settings.VLM_MODEL:
        return _fallback_spend_analysis(uploaded_file.name)

    raw = uploaded_file.read()
    mime_type = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0] or "application/octet-stream"
    data_url = f"data:{mime_type};base64,{base64.b64encode(raw).decode('ascii')}"
    prompt = (
        "업로드된 카드/가계부 이미지 또는 PDF에서 소비 내역을 읽고 카테고리별 월 소비액을 합산하세요. "
        "반드시 JSON만 응답하세요. 형식: "
        "{\"summary\":\"한 줄 요약\",\"rows\":[{\"name\":\"카페\",\"amount\":125000}, ...]} "
        f"카테고리는 다음만 사용하세요: {', '.join(SPEND_CATEGORIES)}. 금액은 원 단위 정수입니다."
    )

    if settings.VLM_API_TYPE == "responses":
        file_content = {"type": "input_image", "image_url": data_url} if mime_type.startswith("image/") else {"type": "input_file", "filename": uploaded_file.name, "file_data": data_url}
        payload = {
            "model": settings.VLM_MODEL,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}, file_content]}],
            "temperature": 0,
        }
    else:
        media_content = {"type": "image_url", "image_url": {"url": data_url}} if mime_type.startswith("image/") else {"type": "file", "file": {"filename": uploaded_file.name, "file_data": data_url}}
        payload = {
            "model": settings.VLM_MODEL,
            "messages": [
                {"role": "developer", "content": "Answer in Korean. Return valid JSON only."},
                {"role": "user", "content": [{"type": "text", "text": prompt}, media_content]},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 1200,
        }

    request = Request(
        settings.VLM_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {settings.GMS_KEY}"},
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        result = json.loads(response.read().decode("utf-8"))

    if "choices" in result:
        content = result["choices"][0]["message"]["content"]
    else:
        content = result.get("output_text") or "".join(
            part.get("text", "")
            for item in result.get("output", [])
            for part in item.get("content", [])
            if isinstance(part, dict)
        )
    parsed = _extract_json_object(content)
    return {"source": "vlm", "summary": parsed.get("summary", "VLM 분석 완료"), "rows": _normalize_spend_rows(parsed.get("rows"))}


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def ai_analyze(request):
    if request.method == "OPTIONS":
        return JsonResponse({})
    if request.FILES.get("file"):
        uploaded_file = request.FILES["file"]
        if uploaded_file.size > 12 * 1024 * 1024:
            return JsonResponse({"error": "12MB 이하의 이미지 또는 PDF만 업로드할 수 있습니다."}, status=400)
        allowed_types = {"image/jpeg", "image/png", "image/heic", "image/heif", "application/pdf"}
        content_type = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0] or ""
        if content_type not in allowed_types:
            return JsonResponse({"error": "JPG, PNG, HEIC, PDF 파일만 분석할 수 있습니다."}, status=400)
        try:
            return JsonResponse(_call_vlm_for_spend(uploaded_file))
        except Exception as exc:
            fallback = _fallback_spend_analysis(uploaded_file.name)
            fallback["error"] = str(exc)
            return JsonResponse(fallback)
    payload = json.loads(request.body or "{}")
    category = payload.get("category", "카페")
    best_card = max(CARDS, key=lambda card: card["match"])
    return JsonResponse(
        {
            "summary": f"{category} 소비 비중이 높고, {best_card['name']} 조합이 가장 잘 맞습니다.",
            "score": best_card["match"],
            "estimatedSaving": best_card["saving"],
            "actions": [f"{category} 결제는 {best_card['name']}로 우선 사용", "실적 구간을 넘는 소비는 무실적 카드로 분산"],
        }
    )
