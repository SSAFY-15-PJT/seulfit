import base64
import json
from urllib.error import HTTPError
import mimetypes
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods


CARDS = [
    {"id": "woori-travel", "name": "?몃옒釉붿썡???곕━移대뱶", "issuer": "?곕━移대뱶", "match": 92, "saving": 32400, "owned": True, "tags": ["移댄럹", "?몄쓽??, "留덊듃"], "benefits": ["移댄럹 50% ?좎씤", "?몄쓽??10% ?좎씤", "留덊듃 5% ?좎씤"]},
    {"id": "toss-check", "name": "?좎뒪諭낇겕 泥댄겕移대뱶", "issuer": "?좎뒪諭낇겕", "match": 88, "saving": 21300, "owned": False, "tags": ["?몄쓽??, "諛곕떖"], "benefits": ["?몄쓽??罹먯떆諛?3%", "移댄럹 罹먯떆諛?2%", "?고쉶鍮??놁쓬"]},
    {"id": "simple-plan", "name": "?좏븳移대뱶 Simple Plan+", "issuer": "?좏븳移대뱶", "match": 78, "saving": 19600, "owned": True, "tags": ["?뚯떇??, "移댄럹"], "benefits": ["?뚯떇??10% ?좎씤", "移댄럹 5% ?좎씤", "?앺솢 ?낆쥌 ?곷┰"]},
]

PROFILE = {
    "name": "源?ы뵿",
    "email": "seulpick@example.com",
    "ownedCards": ["?몃옒釉붿썡???곕━移대뱶", "?좏븳移대뱶 Simple Plan+"],
    "monthlySpend": 800000,
}

YOUTUBE_CATEGORIES = ["?꾩껜", "移대뱶 異붿쿇", "?쒗깮 鍮꾧탳", "?ъ슜 ?꾧린", "鍮꾧탳 遺꾩꽍"]
YOUTUBE_CATEGORY_QUERIES = {
    "?꾩껜": "?좎슜移대뱶 異붿쿇 ?쒗깮 鍮꾧탳",
    "移대뱶 異붿쿇": "?좎슜移대뱶 異붿쿇",
    "?쒗깮 鍮꾧탳": "移대뱶 ?쒗깮 鍮꾧탳",
    "?ъ슜 ?꾧린": "移대뱶 ?ъ슜 ?꾧린",
    "鍮꾧탳 遺꾩꽍": "移대뱶 ?쒗깮 鍮꾧탳 遺꾩꽍",
}
YOUTUBE_POPULAR_KEYWORDS = ["移대뱶 異붿쿇", "?쒗깮 鍮꾧탳", "?고쉶鍮?, "移대뱶 ?뺣━", "?뚮퉬 ?⑦꽩"]
SPEND_CATEGORIES = ["移댄럹", "?몄쓽??, "留덊듃/?덊띁", "?뚯떇??諛곕떖", "?섎쪟/?뚰뭹", "援먰넻", "湲고?"]


def _contains(value, query):
    return query.lower() in value.lower()


def _youtube_get(path, params):
    url = f"https://www.googleapis.com/youtube/v3/{path}?{urlencode(params)}"
    try:
        with urlopen(url, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
            message = payload.get("error", {}).get("message") or body
        except json.JSONDecodeError:
            message = body or str(exc)
        raise RuntimeError(f"YouTube API {exc.code}: {message}") from exc


def _format_view_count(value):
    count = int(value or 0)
    if count >= 10000:
        return f"{round(count / 10000, 1)}留?
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
        {"id": 1, "isExample": True, "title": "[?덉젣] 2026 ?쒗깮 醫뗭? ?좎슜移대뱶 TOP 5", "channel": "移대뱶?뚰겕??, "views": "12留?, "age": "2????, "duration": "8:21", "category": "移대뱶 異붿쿇", "tags": ["移대뱶異붿쿇", "?쒗깮鍮꾧탳"]},
        {"id": 2, "isExample": True, "title": "[?덉젣] ?ы쉶珥덈뀈??移대뱶 異붿쿇 ?뺣━", "channel": "癒몃땲?덉씠??, "views": "6.4留?, "age": "5????, "duration": "10:31", "category": "移대뱶 異붿쿇", "tags": ["泥댄겕移대뱶", "珥덈뀈??]},
        {"id": 3, "isExample": True, "title": "[?덉젣] ??10留뚯썝 ?꾨겮??移대뱶 ?ъ슜踰?, "channel": "?덉빟?섎뒗?쒓렇留?, "views": "5.7留?, "age": "1二???, "duration": "7:12", "category": "?ъ슜 ?꾧린", "tags": ["由щ럭", "移대뱶?뚰겕"]},
        {"id": 4, "isExample": True, "title": "[?덉젣] ??궪???뚮퉬 遺꾩꽍?쇰줈 ?앺솢鍮?以꾩씠湲?, "channel": "SeulPick ?곌뎄??, "views": "9.1留?, "age": "3????, "duration": "9:01", "category": "鍮꾧탳 遺꾩꽍", "tags": ["?곴텒遺꾩꽍", "移대뱶?쒗깮"]},
    ]
    if category != "?꾩껜":
        videos = [video for video in videos if video["category"] == category]
    if query:
        videos = [video for video in videos if _contains(video["title"], query) or _contains(video["channel"], query)]
    for video in videos:
        search_query = query or video["title"].replace("[?덉젣] ", "")
        video["url"] = f"https://www.youtube.com/results?{urlencode({'search_query': search_query})}"
        video["thumbnail"] = ""
    return videos


def _youtube_search(query, category):
    if not settings.YOUTUBE_API_KEY:
        return None
    search_query = query or YOUTUBE_CATEGORY_QUERIES.get(category, YOUTUBE_CATEGORY_QUERIES["?꾩껜"])
    search_data = _youtube_get(
        "search",
        {
            "key": settings.YOUTUBE_API_KEY,
            "part": "snippet",
            "type": "video",
            "maxResults": 9,
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
    return JsonResponse({"area": "?쒖슱 媛뺣궓援???궪??, "linkedSpend": 800000, "recommendedCards": 3, "seulScore": 69.8})


@require_GET
def places(request):
    category = request.GET.get("category", "?꾩껜")
    places_data = [
        {"id": 1, "name": "釉뚮（???ъ씤??, "category": "移댄럹", "distance": 120},
        {"id": 2, "name": "?몃툙??궪??, "category": "?몄쓽??, "distance": 180},
        {"id": 3, "name": "洹몃┛留덊듃 ??궪", "category": "留덊듃", "distance": 260},
    ]
    if category != "?꾩껜":
        places_data = [place for place in places_data if place["category"] == category]
    return JsonResponse({"items": places_data, "categories": ["?꾩껜", "?몄쓽??, "移댄럹", "留덊듃", "?뚯떇??, "?섎쪟/?뚰뭹", "蹂묒썝", "援먯쑁", "湲고?"]})


@require_GET
def recommendations(request):
    spend = int(request.GET.get("spend", PROFILE["monthlySpend"]))
    multiplier = max(spend / PROFILE["monthlySpend"], 0.5)
    return JsonResponse({"items": [{**card, "saving": int(card["saving"] * multiplier)} for card in CARDS], "ownedCards": PROFILE["ownedCards"]})


@require_GET
def videos(request):
    query = request.GET.get("query", "").strip()
    category = request.GET.get("category", "?꾩껜")
    if category not in YOUTUBE_CATEGORIES:
        category = "?꾩껜"
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
            "channels": [{"name": "吏좊룎?큈V"}, {"name": "?ы뀒???곌뎄??}, {"name": "移대뱶???뺤꽍"}, {"name": "?쒗깮 ?곌뎄??}],
            "popularKeywords": YOUTUBE_POPULAR_KEYWORDS,
            "source": source,
            "error": error,
        }
    )


@require_GET
def community(request):
    return JsonResponse({"items": [], "tabs": ["?꾩껜", "?먯쑀寃뚯떆??, "吏덈Ц?듬?", "?숇꽕 ?뺣낫", "?대깽??]})


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
            amount = int(float(str(amount).replace(",", "").replace("??, "").strip() or 0))
        except ValueError:
            amount = 0
        if name == "留덊듃":
            name = "留덊듃/?덊띁"
        if name == "?뚯떇??:
            name = "?뚯떇??諛곕떖"
        if name in SPEND_CATEGORIES:
            by_name[name] = by_name.get(name, 0) + max(0, amount)
    total = sum(by_name.values()) or 1
    return [
        {"name": name, "amount": by_name.get(name, 0), "ratio": round(by_name.get(name, 0) / total * 100)}
        for name in SPEND_CATEGORIES
    ]


def _fallback_spend_analysis(filename="?낅줈???뚯씪"):
    rows = [
        {"name": "移댄럹", "amount": 125000},
        {"name": "?몄쓽??, "amount": 82000},
        {"name": "留덊듃/?덊띁", "amount": 155000},
        {"name": "?뚯떇??諛곕떖", "amount": 202000},
        {"name": "?섎쪟/?뚰뭹", "amount": 135000},
        {"name": "援먰넻", "amount": 102000},
        {"name": "湲고?", "amount": 25000},
    ]
    return {
        "source": "fallback",
        "summary": f"{filename} 遺꾩꽍 ?덉떆瑜?移댄뀒怨좊━蹂??뚮퉬?≪쑝濡??뺣━?덉뒿?덈떎.",
        "rows": _normalize_spend_rows(rows),
    }


def _call_vlm_for_spend(uploaded_file):
    if not settings.GMS_KEY or not settings.VLM_API_URL or not settings.VLM_MODEL:
        return _fallback_spend_analysis(uploaded_file.name)

    raw = uploaded_file.read()
    mime_type = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0] or "application/octet-stream"
    data_url = f"data:{mime_type};base64,{base64.b64encode(raw).decode('ascii')}"
    prompt = (
        "?낅줈?쒕맂 移대뱶/媛怨꾨? ?대?吏 ?먮뒗 PDF?먯꽌 ?뚮퉬 ?댁뿭???쎄퀬 移댄뀒怨좊━蹂????뚮퉬?≪쓣 ?⑹궛?섏꽭?? "
        "諛섎뱶??JSON留??묐떟?섏꽭?? ?뺤떇: "
        "{\"summary\":\"??以??붿빟\",\"rows\":[{\"name\":\"移댄럹\",\"amount\":125000}, ...]} "
        f"移댄뀒怨좊━???ㅼ쓬留??ъ슜?섏꽭?? {', '.join(SPEND_CATEGORIES)}. 湲덉븸? ???⑥쐞 ?뺤닔?낅땲??"
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
    return {"source": "vlm", "summary": parsed.get("summary", "VLM 遺꾩꽍 ?꾨즺"), "rows": _normalize_spend_rows(parsed.get("rows"))}


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def ai_analyze(request):
    if request.method == "OPTIONS":
        return JsonResponse({})
    if request.FILES.get("file"):
        uploaded_file = request.FILES["file"]
        if uploaded_file.size > 12 * 1024 * 1024:
            return JsonResponse({"error": "12MB ?댄븯???대?吏 ?먮뒗 PDF留??낅줈?쒗븷 ???덉뒿?덈떎."}, status=400)
        allowed_types = {"image/jpeg", "image/png", "image/heic", "image/heif", "application/pdf"}
        content_type = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0] or ""
        if content_type not in allowed_types:
            return JsonResponse({"error": "JPG, PNG, HEIC, PDF ?뚯씪留?遺꾩꽍?????덉뒿?덈떎."}, status=400)
        try:
            return JsonResponse(_call_vlm_for_spend(uploaded_file))
        except Exception as exc:
            fallback = _fallback_spend_analysis(uploaded_file.name)
            fallback["error"] = str(exc)
            return JsonResponse(fallback)
    payload = json.loads(request.body or "{}")
    category = payload.get("category", "移댄럹")
    best_card = max(CARDS, key=lambda card: card["match"])
    return JsonResponse(
        {
            "summary": f"{category} ?뚮퉬 鍮꾩쨷???믨퀬, {best_card['name']} 議고빀??媛????留욎뒿?덈떎.",
            "score": best_card["match"],
            "estimatedSaving": best_card["saving"],
            "actions": [f"{category} 寃곗젣??{best_card['name']}濡??곗꽑 ?ъ슜", "?ㅼ쟻 援ш컙???섎뒗 ?뚮퉬??臾댁떎??移대뱶濡?遺꾩궛"],
        }
    )
