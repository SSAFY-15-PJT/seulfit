from django.conf import settings
from django.db.models import Q

from .card_gorilla_activation import collect_display_only_conditions
from .graph_sync import parse_card_graph_key
from .models import CardProduct, CrawlStatus, ParseStatus


def _to_float(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_graph_signal_map(candidates):
    grouped = {}
    max_store_count = max(
        (_to_float(item.get("store_count")) for item in candidates),
        default=0,
    )

    for candidate in candidates:
        parsed_key = parse_card_graph_key(candidate.get("card_key"))
        category = candidate.get("category_key")
        if not parsed_key or not category:
            continue
        key = tuple(sorted(parsed_key.items()))
        signal = grouped.setdefault(
            key,
            {
                "matched_categories": set(),
                "category_store_counts": {},
                "category_shares": {},
                "top_category": None,
                "top_store_count": 0,
                "score": 0,
            },
        )
        store_count = _to_float(candidate.get("store_count"))
        category_share = _to_float(candidate.get("category_share"))
        density_score = (
            store_count / max_store_count * 100 if max_store_count else 0
        )
        category_score = category_share * 100 * 0.6 + density_score * 0.4
        signal["matched_categories"].add(category)
        signal["category_store_counts"][category] = int(store_count)
        signal["category_shares"][category] = round(category_share, 4)
        signal["score"] = max(signal["score"], category_score)
        if store_count > signal["top_store_count"]:
            signal["top_store_count"] = store_count
            signal["top_category"] = category

    normalized = {}
    for key, signal in grouped.items():
        normalized[key] = {
            "graph_rerank_score": round(signal["score"], 1),
            "graph_top_category": signal["top_category"],
            "graph_matched_categories": sorted(signal["matched_categories"]),
            "graph_category_store_counts": signal["category_store_counts"],
            "graph_category_shares": signal["category_shares"],
        }
    return normalized


def card_product_to_recommendation_input(card):
    primary_image = (
        card.images.filter(
            download_status=CrawlStatus.SUCCESS,
            is_primary=True,
        ).first()
        or card.images.filter(download_status=CrawlStatus.SUCCESS).first()
    )
    if primary_image and primary_image.local_path:
        image_url = f"{settings.MEDIA_URL.rstrip('/')}/{primary_image.local_path}"
    elif primary_image:
        image_url = primary_image.source_url
    else:
        image_url = ""

    benefits = [
        {
            "category": benefit.category,
            "benefit_group": benefit.benefit_group,
            "discount_type": benefit.discount_type,
            "discount_rate": (
                float(benefit.discount_rate)
                if benefit.discount_rate is not None
                else None
            ),
            "discount_amount": benefit.discount_amount,
            "minimum_transaction_amount": benefit.minimum_transaction_amount,
            "maximum_transaction_amount": benefit.maximum_transaction_amount,
            "per_transaction_limit": benefit.per_transaction_limit,
            "daily_benefit_limit": benefit.daily_benefit_limit,
            "daily_usage_limit": benefit.daily_usage_limit,
            "monthly_usage_limit": benefit.monthly_usage_limit,
            "estimated_monthly_uses": benefit.estimated_monthly_uses,
            "category_monthly_limit": benefit.category_monthly_limit,
            "merchant_scope": benefit.merchant_scope,
            "channel": benefit.channel,
            "start_hour": benefit.start_hour,
            "end_hour": benefit.end_hour,
            "display_only_conditions": collect_display_only_conditions(benefit),
            "calculation_blockers": sorted(
                set(benefit.unsupported_conditions or [])
                - set(collect_display_only_conditions(benefit))
            ),
        }
        for benefit in card.benefits.filter(parse_status=ParseStatus.ACTIVE)
    ]
    benefit_tiers = [
        {
            "scope": tier.scope,
            "minimum_spending": tier.minimum_spending,
            "maximum_spending": tier.maximum_spending,
            "monthly_discount_limit": tier.monthly_discount_limit,
        }
        for tier in card.benefit_tiers.filter(parse_status=ParseStatus.VALIDATED)
    ]
    service_limit_tiers = [
        {
            "benefit_group": tier.benefit_group,
            "minimum_spending": tier.minimum_spending,
            "maximum_spending": tier.maximum_spending,
            "monthly_spending_limit": tier.monthly_spending_limit,
            "monthly_discount_limit": tier.monthly_discount_limit,
            "monthly_usage_limit": tier.monthly_usage_limit,
        }
        for tier in card.service_limit_tiers.filter(
            parse_status=ParseStatus.VALIDATED
        )
    ]

    return {
        "id": card.pk,
        "external_id": card.external_id,
        "name": card.name,
        "issuer": card.issuer,
        "provider": card.provider,
        "card_type": card.card_type,
        "image_url": image_url,
        "source_url": card.source_url,
        "focus": sorted({benefit["category"] for benefit in benefits}),
        "annual_fee": card.annual_fee,
        "annual_fee_source_url": card.annual_fee_source_url,
        "annual_fee_verified_at": (
            card.annual_fee_verified_at.isoformat()
            if card.annual_fee_verified_at
            else None
        ),
        "previous_month_requirement": card.previous_month_requirement,
        "monthly_discount_limit": card.monthly_discount_limit,
        "benefits": benefits,
        "benefit_tiers": benefit_tiers,
        "service_limit_tiers": service_limit_tiers,
    }


def load_recommendation_candidates(area_id=None):
    recommendation_source = "sqlite"
    graph_card_filters = None
    graph_signal_map = {}
    graph_candidate_count = None
    graph_status = "not_requested"
    graph_fallback_reason = None

    if area_id:
        graph_status = "requested"
        try:
            from .graph_repository import GraphRepository
            repo = GraphRepository()
            candidates = repo.find_card_candidates_by_area(area_id)
            graph_candidate_count = len(candidates)
            if candidates:
                graph_signal_map = _build_graph_signal_map(candidates)
                parsed_keys = []
                for candidate in candidates:
                    parsed_key = parse_card_graph_key(candidate["card_key"])
                    if parsed_key:
                        parsed_keys.append(parsed_key)
                graph_card_filters = Q(pk__in=[])
                for parsed_key in parsed_keys:
                    graph_card_filters |= Q(**parsed_key)
                recommendation_source = "neo4j"
                graph_status = "matched"
            else:
                graph_status = "no_candidates"
                graph_fallback_reason = "no_graph_candidates"
        except Exception:
            # Neo4j is a candidate-generation layer; SQLite remains the safe source of record.
            graph_status = "unavailable"
            graph_fallback_reason = "neo4j_unavailable"

    queryset = CardProduct.objects.filter(
        parse_status=ParseStatus.ACTIVE,
        annual_fee__isnull=False,
        benefits__parse_status=ParseStatus.ACTIVE,
    )
    if graph_card_filters is not None:
        queryset = queryset.filter(graph_card_filters)

    cards = list(
        queryset
        .distinct()
        .prefetch_related(
            "benefits",
            "benefit_tiers",
            "service_limit_tiers",
            "images",
        )
        .order_by("pk")
    )
    ready_ids = [card.pk for card in cards]
    unready_count = CardProduct.objects.filter(
        parse_status=ParseStatus.ACTIVE
    ).exclude(pk__in=ready_ids).count()
    review_count = CardProduct.objects.filter(
        parse_status=ParseStatus.REVIEW_REQUIRED
    ).count()
    invalid_count = CardProduct.objects.filter(
        parse_status=ParseStatus.INVALID
    ).count()
    inactive_count = CardProduct.objects.filter(
        parse_status=ParseStatus.INACTIVE
    ).count()

    return {
        "cards": [
            {
                **card_product_to_recommendation_input(card),
                **graph_signal_map.get(
                    tuple(
                        sorted(
                            {
                                "source_channel": card.source_channel,
                                "external_id": card.external_id,
                            }.items()
                        )
                    ),
                    {},
                ),
            }
            for card in cards
        ],
        "metadata": {
            "recommendation_source": recommendation_source,
            "candidate_count": len(cards),
            "excluded_review_count": review_count,
            "excluded_invalid_count": invalid_count,
            "excluded_inactive_count": inactive_count,
            "excluded_unready_count": unready_count,
            "graph_candidate_count": graph_candidate_count,
            "graph_status": graph_status,
            "graph_fallback_reason": graph_fallback_reason,
            "fallback_reason": "no_active_cards" if not cards else None,
        },
    }


def serialize_card_product(card):
    data = card_product_to_recommendation_input(card)
    data["benefits"] = [
        {
            "id": benefit.pk,
            "category": benefit.category,
            "benefit_group": benefit.benefit_group,
            "discount_type": benefit.discount_type,
            "discount_rate": (
                float(benefit.discount_rate)
                if benefit.discount_rate is not None
                else None
            ),
            "discount_amount": benefit.discount_amount,
            "minimum_transaction_amount": benefit.minimum_transaction_amount,
            "maximum_transaction_amount": benefit.maximum_transaction_amount,
            "per_transaction_limit": benefit.per_transaction_limit,
            "daily_benefit_limit": benefit.daily_benefit_limit,
            "monthly_usage_limit": benefit.monthly_usage_limit,
            "merchant_scope": benefit.merchant_scope,
            "channel": benefit.channel,
            "start_hour": benefit.start_hour,
            "end_hour": benefit.end_hour,
            "parse_status": benefit.parse_status,
            "unsupported_conditions": benefit.unsupported_conditions,
            "raw_text": benefit.raw_text,
            "display_only_conditions": collect_display_only_conditions(benefit),
            "calculation_blockers": sorted(
                set(benefit.unsupported_conditions or [])
                - set(collect_display_only_conditions(benefit))
            ),
        }
        for benefit in card.benefits.all()
    ]
    data.update(
        {
            "parse_status": card.parse_status,
            "review_reasons": card.review_reasons,
            "validation_errors": card.validation_errors,
        }
    )
    return data
