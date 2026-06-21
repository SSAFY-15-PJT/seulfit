from django.conf import settings

from .card_gorilla_activation import collect_display_only_conditions
from .models import CardProduct, CrawlStatus, ParseStatus


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


def load_recommendation_candidates():
    cards = list(
        CardProduct.objects.filter(
            parse_status=ParseStatus.ACTIVE,
            annual_fee__isnull=False,
            benefits__parse_status=ParseStatus.ACTIVE,
        )
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
        "cards": [card_product_to_recommendation_input(card) for card in cards],
        "metadata": {
            "recommendation_source": "sqlite",
            "candidate_count": len(cards),
            "excluded_review_count": review_count,
            "excluded_invalid_count": invalid_count,
            "excluded_inactive_count": inactive_count,
            "excluded_unready_count": unready_count,
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
