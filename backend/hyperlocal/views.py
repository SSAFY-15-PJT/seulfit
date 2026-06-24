from django.db.models import Count
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.graph_sync import build_card_graph_key
from finance.models import CardProduct
from .services import (
    build_area_id_from_coordinates,
    get_map_summary,
    parse_consumption_image,
    simulate_cards,
    sync_area_graph_for_coordinates,
)
from users.models import UserCardEvent, UserConsumptionProfile, UserOwnedCard


CATEGORY_KEY_ALIASES = {
    "카페": "cafe",
    "편의점": "convenience",
    "외식": "dining",
    "음식점": "dining",
    "배달": "delivery",
    "마트": "mart",
    "쇼핑": "shopping",
    "기타": "etc",
    "CE7": "cafe",
    "CS2": "convenience",
    "FD6": "dining",
    "MT1": "mart",
}
SUPPORTED_RECOMMENDATION_CATEGORIES = {
    "cafe",
    "convenience",
    "dining",
    "delivery",
    "mart",
    "shopping",
}
EVENT_POPULARITY_WEIGHTS = {
    "viewed": 1,
    "clicked": 3,
    "liked": 5,
    "applied_for": 10,
    "dismissed": -2,
}


def normalize_infrastructure(infrastructure):
    if isinstance(infrastructure, dict):
        normalized = {}
        for key, value in infrastructure.items():
            canonical_key = CATEGORY_KEY_ALIASES.get(str(key), str(key))
            normalized[canonical_key] = value
        return normalized
    if isinstance(infrastructure, list):
        normalized = {}
        for item in infrastructure:
            if not isinstance(item, dict):
                continue
            category = item.get("key") or item.get("category") or item.get("code")
            if not category:
                continue
            canonical_key = CATEGORY_KEY_ALIASES.get(str(category), str(category))
            normalized[canonical_key] = {
                "count": item.get("count", item.get("store_count", 0)),
                "total_count": item.get(
                    "total_count",
                    item.get("count", item.get("store_count", 0)),
                ),
                "sample_count": item.get("sample_count", 0),
                "is_sampled": item.get("is_sampled", False),
                "merchant_counts": item.get("merchant_counts", {}),
            }
        return normalized
    return {}


def normalize_selected_category(category):
    if not category:
        return None
    normalized = CATEGORY_KEY_ALIASES.get(str(category), str(category))
    return (
        normalized
        if normalized in SUPPORTED_RECOMMENDATION_CATEGORIES
        else None
    )


def is_truthy(value):
    return value is True or str(value).lower() in {"1", "true", "yes", "on"}


def to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_card_context(payload):
    if isinstance(payload, dict):
        card_id = payload.get("card_id") or payload.get("id")
        return {
            "card_id": card_id,
            "graph_matched_categories": payload.get("graph_matched_categories")
            or payload.get("matched_categories")
            or [],
            "graph_category_shares": payload.get("graph_category_shares")
            or payload.get("category_shares")
            or {},
            "graph_rerank_score": to_float(payload.get("graph_rerank_score")),
            "seul_score": to_float(
                payload.get("seul_score") or payload.get("ranking_score")
            ),
        }
    return {
        "card_id": payload,
        "graph_matched_categories": [],
        "graph_category_shares": {},
        "graph_rerank_score": 0.0,
        "seul_score": 0.0,
    }


def calculate_category_fit(card_context):
    shares = card_context.get("graph_category_shares") or {}
    matched_categories = card_context.get("graph_matched_categories") or []
    if not isinstance(shares, dict):
        shares = {}
    category_fit = sum(to_float(shares.get(category)) for category in matched_categories)
    return round(category_fit, 4)


def sync_user_graph_profile(user_id, area_id, area_name, owned_card_ids):
    if not user_id:
        return {
            "user_graph_status": "not_requested",
            "user_graph_owned_card_count": None,
            "user_graph_error": None,
        }

    from finance.graph_repository import GraphRepository

    cards = CardProduct.objects.filter(pk__in=owned_card_ids or [])
    owned_card_keys = [build_card_graph_key(card) for card in cards]
    GraphRepository().sync_user_profile(
        user_id=user_id,
        preferred_area_id=area_id,
        preferred_area_name=area_name,
        owned_card_keys=owned_card_keys,
    )
    return {
        "user_graph_status": "synced",
        "user_graph_owned_card_count": len(owned_card_keys),
        "user_graph_error": None,
    }


class ParseImageView(APIView):
    def post(self, request):
        uploaded_file = request.FILES.get("image")
        parsed = parse_consumption_image(uploaded_file)
        return Response(parsed)


class CardEventView(APIView):
    def post(self, request):
        user_id = request.data.get("user_id")
        card_id = request.data.get("card_id")
        event_type = request.data.get("event_type")
        area_id = request.data.get("area_id") or ""
        metadata = request.data.get("metadata") or {}
        is_demo = is_truthy(request.data.get("is_demo", False))

        if event_type not in dict(UserCardEvent.EVENT_TYPES):
            return Response(
                {"event_status": "invalid_event_type"},
                status=400,
            )
        try:
            card = CardProduct.objects.get(pk=card_id)
        except CardProduct.DoesNotExist:
            return Response({"event_status": "card_not_found"}, status=404)

        event = UserCardEvent.objects.create(
            user_id=user_id,
            card=card,
            area_id=area_id,
            event_type=event_type,
            metadata_json=metadata,
            is_demo=is_demo,
        )

        try:
            from finance.graph_repository import GraphRepository

            GraphRepository().create_user_card_event(
                user_id=user_id,
                card_key=build_card_graph_key(card),
                event_type=event_type,
                area_id=area_id,
                metadata=metadata,
                is_demo=is_demo,
            )
            event.graph_sync_status = "synced"
            event.graph_sync_error = ""
            event.save(update_fields=["graph_sync_status", "graph_sync_error"])
            event_status = "synced"
            graph_error = None
        except Exception as exc:
            event.graph_sync_status = "failed"
            event.graph_sync_error = str(exc)
            event.save(update_fields=["graph_sync_status", "graph_sync_error"])
            event_status = "saved_graph_failed"
            graph_error = str(exc)

        return Response(
            {
                "event_status": event_status,
                "event_id": event.pk,
                "event_type": event.event_type,
                "user_id": event.user_id,
                "card_id": event.card_id,
                "area_id": event.area_id,
                "graph_sync_status": event.graph_sync_status,
                "graph_sync_error": graph_error,
            },
            status=201,
        )


class AreaCardPopularityView(APIView):
    def post(self, request):
        area_id = request.data.get("area_id") or ""
        raw_cards = request.data.get("cards")
        if raw_cards is None:
            raw_cards = request.data.get("card_ids") or []
        card_contexts = [normalize_card_context(item) for item in raw_cards]
        card_contexts = [
            context for context in card_contexts if context.get("card_id") is not None
        ]
        card_ids = [context["card_id"] for context in card_contexts]

        if not area_id:
            return Response({"error": "area_id is required"}, status=400)
        if not card_ids:
            return Response({"error": "cards or card_ids are required"}, status=400)

        event_rows = (
            UserCardEvent.objects.filter(area_id=area_id, card_id__in=card_ids)
            .values("card_id", "event_type")
            .annotate(count=Count("id"))
        )
        event_counts_by_card = {
            card_id: {event_type: 0 for event_type in EVENT_POPULARITY_WEIGHTS}
            for card_id in card_ids
        }
        for row in event_rows:
            if row["event_type"] in EVENT_POPULARITY_WEIGHTS:
                event_counts_by_card.setdefault(
                    row["card_id"],
                    {event_type: 0 for event_type in EVENT_POPULARITY_WEIGHTS},
                )[row["event_type"]] = row["count"]

        ranking = []
        for context in card_contexts:
            card_id = context["card_id"]
            event_counts = event_counts_by_card.get(
                card_id,
                {event_type: 0 for event_type in EVENT_POPULARITY_WEIGHTS},
            )
            event_score = sum(
                event_counts.get(event_type, 0) * weight
                for event_type, weight in EVENT_POPULARITY_WEIGHTS.items()
            )
            category_fit = calculate_category_fit(context)
            local_popularity_score = round(event_score * (1 + category_fit), 2)
            ranking.append(
                {
                    "card_id": card_id,
                    "event_score": event_score,
                    "category_fit": category_fit,
                    "local_popularity_score": local_popularity_score,
                    "event_counts": event_counts,
                    "graph_rerank_score": context["graph_rerank_score"],
                    "seul_score": context["seul_score"],
                    "matched_categories": context["graph_matched_categories"],
                }
            )

        ranking.sort(
            key=lambda item: (
                item["local_popularity_score"],
                item["graph_rerank_score"],
                item["seul_score"],
            ),
            reverse=True,
        )
        return Response(
            {
                "area_id": area_id,
                "event_weights": EVENT_POPULARITY_WEIGHTS,
                "ranking": ranking,
            }
        )


class SimulateView(APIView):
    def post(self, request):
        user_id = request.data.get("user_id")
        spending = request.data.get("spending")
        infrastructure = normalize_infrastructure(request.data.get("infrastructure"))
        area_id = request.data.get("area_id")
        lat = request.data.get("lat")
        lng = request.data.get("lng")
        radius = request.data.get("radius", 500)
        sync_area = is_truthy(request.data.get("sync_area", False))
        area_sync_result = {
            "area_sync_status": "not_requested",
            "area_sync_store_count": None,
            "area_sync_error": None,
        }
        if sync_area and lat is not None and lng is not None:
            area_id = area_id or build_area_id_from_coordinates(lat, lng)
            area_name = request.data.get("area_name") or f"selected_{area_id}"
            try:
                area_sync_result = sync_area_graph_for_coordinates(
                    area_id=area_id,
                    area_name=area_name,
                    lat=lat,
                    lng=lng,
                    radius=radius,
                )
            except Exception as exc:
                area_sync_result = {
                    "area_sync_status": "failed",
                    "area_sync_store_count": None,
                    "area_sync_error": str(exc),
                }
        previous_month_spending = request.data.get("previous_month_spending")
        owned_card_ids = request.data.get("owned_card_ids")
        transactions = request.data.get("transactions")
        spending_source = request.data.get("spending_source")
        if spending is None and user_id:
            profile = (
                UserConsumptionProfile.objects.filter(user_id=user_id)
                .order_by("-last_updated_at")
                .first()
            )
            if profile:
                spending = profile.spending_json
                spending_source = spending_source or profile.source
        if owned_card_ids is None and user_id:
            owned_card_ids = list(
                UserOwnedCard.objects.filter(user_id=user_id).values_list(
                    "card_id",
                    flat=True,
                )
            )
        if owned_card_ids is None:
            owned_card_ids = []
        area_name = request.data.get("area_name") or (
            f"selected_{area_id}" if area_id else None
        )
        user_graph_result = {
            "user_graph_status": "not_requested",
            "user_graph_owned_card_count": None,
            "user_graph_error": None,
        }
        if user_id and area_id:
            try:
                user_graph_result = sync_user_graph_profile(
                    user_id=user_id,
                    area_id=area_id,
                    area_name=area_name,
                    owned_card_ids=owned_card_ids,
                )
            except Exception as exc:
                user_graph_result = {
                    "user_graph_status": "failed",
                    "user_graph_owned_card_count": None,
                    "user_graph_error": str(exc),
                }
        selected_category = normalize_selected_category(
            request.data.get("selected_category")
        )
        allow_mock_fallback = request.data.get("allow_mock_fallback", False) is True
        simulation = simulate_cards(
            spending=spending,
            infrastructure=infrastructure,
            area_id=area_id,
            previous_month_spending=previous_month_spending,
            owned_card_ids=owned_card_ids,
            transactions=transactions,
            spending_source=spending_source,
            selected_category=selected_category,
            allow_mock_fallback=allow_mock_fallback,
        )
        ranking = simulation["ranking"]
        spending_profile = ranking[0]["spending_profile"] if ranking else None
        previous_month_spending_profile = (
            ranking[0]["previous_month_spending_profile"] if ranking else None
        )
        return Response(
            {
                "spending": spending,
                "user_id": user_id,
                "area_id": area_id,
                "lat": lat,
                "lng": lng,
                "radius": radius,
                **area_sync_result,
                **user_graph_result,
                "spending_profile": spending_profile,
                "previous_month_spending": (
                    previous_month_spending_profile["amount"]
                    if previous_month_spending_profile
                    else previous_month_spending
                ),
                "previous_month_spending_profile": previous_month_spending_profile,
                "owned_card_ids": owned_card_ids,
                "selected_category": selected_category,
                "card_ranking_list": ranking,
                "best_card": ranking[0] if ranking else None,
                **simulation["metadata"],
            }
        )


class MapSummaryView(APIView):
    def get(self, request):
        lat = request.query_params.get("lat", 37.4979)
        lng = request.query_params.get("lng", 127.0276)
        radius = request.query_params.get("radius", 500)
        return Response(get_map_summary(lat=lat, lng=lng, radius=radius))


class WeatherCurationView(APIView):
    def get(self, request):
        return Response(
            {
                "temperature_celsius": 32.5,
                "condition": "맑음",
                "message": "강남역 주변 카페 밀도가 높아요. 오늘은 카페 할인 강점이 있는 카드를 우선 추천합니다.",
            }
        )
