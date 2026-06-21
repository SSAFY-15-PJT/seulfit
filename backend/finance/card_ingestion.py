from hashlib import sha256

from django.db import transaction
from django.utils import timezone

from .card_schema import validate_card_product
from .models import (
    BenefitRule,
    CardBenefitTier,
    CardServiceLimitTier,
    CardImage,
    CardProduct,
    CrawlSnapshot,
    CrawlStatus,
    ParseStatus,
)


@transaction.atomic
def persist_parsed_card(crawl_item, parsed, raw_html):
    validation = validate_card_product(parsed)
    if parsed.get("review_reasons"):
        if validation.parse_status != ParseStatus.INVALID:
            validation.parse_status = ParseStatus.REVIEW_REQUIRED
        validation.review_reasons.extend(parsed["review_reasons"])
    if parsed.get("parse_status_override") == ParseStatus.INACTIVE:
        validation.parse_status = ParseStatus.INACTIVE
    normalized = validation.normalized_data
    normalized["parse_status"] = validation.parse_status
    existing_card = CardProduct.objects.filter(
        source_channel=normalized["source_channel"],
        external_id=normalized["external_id"],
    ).first()
    annual_fee_is_verified = bool(
        existing_card and existing_card.annual_fee_verified_at
    )
    discovered_fee_source = normalized.get("annual_fee_source_url", "")
    discovered_fee_is_verified = bool(
        normalized.get("annual_fee") is not None and discovered_fee_source
    )
    preserve_active_status = bool(
        annual_fee_is_verified
        and existing_card.parse_status == ParseStatus.ACTIVE
        and validation.parse_status
        not in (ParseStatus.INVALID, ParseStatus.INACTIVE)
    )
    effective_parse_status = (
        ParseStatus.ACTIVE
        if preserve_active_status
        else validation.parse_status
    )
    review_reasons = sorted(
        reason
        for reason in set(validation.review_reasons)
        if not (
            annual_fee_is_verified
            and "연회비" in reason
        )
    )
    if preserve_active_status:
        review_reasons = [
            "일부 혜택은 계산 미지원으로 추천 금액에서 제외됨"
        ]

    card, _ = CardProduct.objects.update_or_create(
        source_channel=normalized["source_channel"],
        external_id=normalized["external_id"],
        defaults={
            "issuer": normalized["issuer"],
            "provider": normalized["provider"],
            "card_type": normalized["card_type"],
            "name": normalized["name"],
            "source_url": normalized["source_url"],
            "annual_fee": (
                existing_card.annual_fee
                if annual_fee_is_verified
                else normalized["annual_fee"]
            ),
            "annual_fee_source_url": (
                existing_card.annual_fee_source_url
                if annual_fee_is_verified
                else discovered_fee_source
            ),
            "annual_fee_verified_at": (
                existing_card.annual_fee_verified_at
                if annual_fee_is_verified
                else timezone.now()
                if discovered_fee_is_verified
                else None
            ),
            "previous_month_requirement": normalized[
                "previous_month_requirement"
            ],
            "monthly_discount_limit": normalized["monthly_discount_limit"],
            "parse_status": effective_parse_status,
            "raw_text": normalized["raw_text"],
            "validation_errors": validation.errors,
            "review_reasons": review_reasons,
            "collected_at": timezone.now(),
        },
    )

    card.benefits.all().delete()
    BenefitRule.objects.bulk_create(
        [
            BenefitRule(
                card=card,
                category=benefit["category"],
                benefit_group=benefit.get("benefit_group", ""),
                discount_type=benefit["discount_type"],
                discount_rate=benefit.get("discount_rate"),
                discount_amount=benefit.get("discount_amount"),
                minimum_transaction_amount=benefit.get(
                    "minimum_transaction_amount", 0
                ),
                maximum_transaction_amount=benefit.get(
                    "maximum_transaction_amount"
                ),
                per_transaction_limit=benefit.get("per_transaction_limit"),
                daily_benefit_limit=benefit.get("daily_benefit_limit"),
                daily_usage_limit=benefit.get("daily_usage_limit"),
                monthly_usage_limit=benefit.get("monthly_usage_limit"),
                estimated_monthly_uses=benefit.get("estimated_monthly_uses"),
                category_monthly_limit=benefit.get("category_monthly_limit"),
                merchant_scope=benefit.get("merchant_scope", []),
                channel=benefit.get("channel", "all"),
                start_hour=benefit.get("start_hour"),
                end_hour=benefit.get("end_hour"),
                condition_text=benefit.get("condition_text", ""),
                exclusion_text=benefit.get("exclusion_text", ""),
                raw_text=benefit["raw_text"],
                parse_status=benefit["parse_status"],
                unsupported_conditions=benefit.get(
                    "unsupported_conditions", []
                ),
            )
            for benefit in normalized["benefits"]
            if benefit["parse_status"] != "invalid"
        ]
    )

    card.benefit_tiers.all().delete()
    CardBenefitTier.objects.bulk_create(
        [
            CardBenefitTier(
                card=card,
                scope=tier["scope"],
                minimum_spending=tier["minimum_spending"],
                maximum_spending=tier["maximum_spending"],
                monthly_discount_limit=tier["monthly_discount_limit"],
                raw_text=tier["raw_text"],
                parse_status=tier["parse_status"],
            )
            for tier in normalized.get("benefit_tiers", [])
            if tier["parse_status"] != ParseStatus.INVALID
        ]
    )

    card.service_limit_tiers.all().delete()
    CardServiceLimitTier.objects.bulk_create(
        [
            CardServiceLimitTier(
                card=card,
                benefit_group=tier["benefit_group"],
                minimum_spending=tier["minimum_spending"],
                maximum_spending=tier["maximum_spending"],
                monthly_spending_limit=tier["monthly_spending_limit"],
                monthly_discount_limit=tier["monthly_discount_limit"],
                monthly_usage_limit=tier["monthly_usage_limit"],
                raw_text=tier["raw_text"],
                parse_status=tier["parse_status"],
            )
            for tier in normalized.get("service_limit_tiers", [])
            if tier["parse_status"] != ParseStatus.INVALID
        ]
    )

    for index, image in enumerate(parsed.get("images", [])):
        card_image, created = CardImage.objects.get_or_create(
            card=card,
            source_url=image["source_url"],
            defaults={
                "alt_text": image.get("alt_text", ""),
                "is_primary": index == 0,
                "download_status": CrawlStatus.PENDING,
            },
        )
        if not created:
            card_image.alt_text = image.get("alt_text", "")
            card_image.is_primary = index == 0
            card_image.save(
                update_fields=["alt_text", "is_primary", "updated_at"]
            )

    CrawlSnapshot.objects.create(
        crawl_item=crawl_item,
        card=card,
        source_url=parsed["source_url"],
        raw_html=raw_html,
        content_checksum=sha256(raw_html.encode("utf-8")).hexdigest(),
    )
    return card, validation
