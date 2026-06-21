from dataclasses import dataclass

from .card_schema import validate_benefit_rule
from .models import ParseStatus


@dataclass(frozen=True)
class ActivationResult:
    is_ready: bool
    blockers: list[str]
    warnings: list[str]


def evaluate_card_activation(card):
    blockers = []
    warnings = []
    if card.annual_fee is None:
        blockers.append("annual_fee_missing")
    if card.validation_errors:
        blockers.append("card_validation_errors")
    if not card.benefits.filter(parse_status=ParseStatus.ACTIVE).exists():
        blockers.append("no_active_benefits")
    if card.benefits.filter(parse_status=ParseStatus.REVIEW_REQUIRED).exists():
        warnings.append("partial_benefit_coverage")
    if card.benefits.filter(parse_status=ParseStatus.INVALID).exists():
        blockers.append("invalid_benefits")
    return ActivationResult(
        is_ready=not blockers,
        blockers=blockers,
        warnings=warnings,
    )


def revalidate_card_benefits(card):
    for benefit in card.benefits.all():
        result = validate_benefit_rule(
            {
                "category": benefit.category,
                "benefit_group": benefit.benefit_group,
                "discount_type": benefit.discount_type,
                "discount_rate": benefit.discount_rate,
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
                "condition_text": benefit.condition_text,
                "exclusion_text": benefit.exclusion_text,
                "raw_text": benefit.raw_text,
                "unsupported_conditions": benefit.unsupported_conditions,
            }
        )
        benefit.parse_status = result.parse_status
        benefit.unsupported_conditions = result.normalized_data[
            "unsupported_conditions"
        ]
        benefit.save(
            update_fields=[
                "parse_status",
                "unsupported_conditions",
                "updated_at",
            ]
        )


def activate_card_if_ready(card):
    result = evaluate_card_activation(card)
    if result.is_ready and card.parse_status != ParseStatus.ACTIVE:
        card.parse_status = ParseStatus.ACTIVE
        card.review_reasons = (
            ["일부 혜택은 계산 미지원으로 추천 금액에서 제외됨"]
            if result.warnings
            else []
        )
        card.save(
            update_fields=["parse_status", "review_reasons", "updated_at"]
        )
    return result
