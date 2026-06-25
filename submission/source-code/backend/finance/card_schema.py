from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import re

from .models import CardType, DiscountType, ParseStatus


SUPPORTED_CATEGORIES = {
    "cafe",
    "convenience",
    "mart",
    "food",
    "dining",
    "delivery",
    "shopping",
    "etc",
}
SUPPORTED_CHANNELS = {"all", "online", "offline"}
UNSUPPORTED_CONDITION_FIELDS = {
    "merchant_scope",
    "weekday_condition",
    "random_reward",
    "exclusion_text",
    "category_mapping",
    "source_review_required",
    "usage_limit_mapping",
    "mixed_channel_mapping",
    "payment_method_condition",
}


@dataclass
class ValidationResult:
    is_valid: bool
    parse_status: str
    normalized_data: dict
    errors: list[str] = field(default_factory=list)
    review_reasons: list[str] = field(default_factory=list)


DELIVERY_KEYWORDS = (
    "배달",
    "배달앱",
    "배달의민족",
    "요기요",
    "쿠팡이츠",
    "땡겨요",
)


def canonicalize_category(category, raw_text=""):
    if category != "food":
        return category
    normalized_text = str(raw_text or "")
    if any(keyword in normalized_text for keyword in DELIVERY_KEYWORDS):
        return "delivery"
    return "dining"


def _non_negative_integer(value, field_name, errors, allow_none=False):
    if value in (None, "") and allow_none:
        return None
    try:
        normalized = int(value or 0)
    except (TypeError, ValueError):
        errors.append(f"{field_name}: 0 이상의 정수여야 함")
        return 0
    if normalized < 0:
        errors.append(f"{field_name}: 음수일 수 없음")
    return normalized


def validate_benefit_tier(tier):
    errors = []
    normalized = dict(tier)
    normalized["scope"] = normalized.get("scope") or "card_total"
    normalized["minimum_spending"] = _non_negative_integer(
        normalized.get("minimum_spending"),
        "minimum_spending",
        errors,
    )
    normalized["maximum_spending"] = _non_negative_integer(
        normalized.get("maximum_spending"),
        "maximum_spending",
        errors,
        allow_none=True,
    )
    normalized["monthly_discount_limit"] = _non_negative_integer(
        normalized.get("monthly_discount_limit"),
        "monthly_discount_limit",
        errors,
    )
    if (
        normalized["maximum_spending"] is not None
        and normalized["maximum_spending"] <= normalized["minimum_spending"]
    ):
        errors.append("maximum_spending: minimum_spending보다 커야 함")
    if not normalized.get("raw_text"):
        errors.append("raw_text: 원문이 필요함")
    status = ParseStatus.INVALID if errors else ParseStatus.VALIDATED
    normalized["parse_status"] = status
    return ValidationResult(
        is_valid=not errors,
        parse_status=status,
        normalized_data=normalized,
        errors=errors,
    )


def validate_service_limit_tier(tier):
    errors = []
    normalized = dict(tier)
    if not normalized.get("benefit_group"):
        errors.append("benefit_group: 필수값")
    for field_name in ("minimum_spending",):
        normalized[field_name] = _non_negative_integer(
            normalized.get(field_name),
            field_name,
            errors,
        )
    for field_name in (
        "maximum_spending",
        "monthly_spending_limit",
        "monthly_discount_limit",
        "monthly_usage_limit",
    ):
        normalized[field_name] = _non_negative_integer(
            normalized.get(field_name),
            field_name,
            errors,
            allow_none=True,
        )
    if (
        normalized["maximum_spending"] is not None
        and normalized["maximum_spending"] <= normalized["minimum_spending"]
    ):
        errors.append("maximum_spending: minimum_spending보다 커야 함")
    if not any(
        normalized.get(field_name) is not None
        for field_name in (
            "monthly_spending_limit",
            "monthly_discount_limit",
            "monthly_usage_limit",
        )
    ):
        errors.append("서비스 한도 값이 하나 이상 필요함")
    if not normalized.get("raw_text"):
        errors.append("raw_text: 원문이 필요함")
    status = ParseStatus.INVALID if errors else ParseStatus.VALIDATED
    normalized["parse_status"] = status
    return ValidationResult(
        is_valid=not errors,
        parse_status=status,
        normalized_data=normalized,
        errors=errors,
    )


def validate_benefit_rule(rule):
    errors = []
    review_reasons = []
    normalized = dict(rule)
    category = canonicalize_category(
        normalized.get("category"),
        normalized.get("raw_text"),
    )
    normalized["category"] = category
    discount_type = normalized.get("discount_type")

    if category not in SUPPORTED_CATEGORIES:
        errors.append(f"category: 지원하지 않는 카테고리 {category!r}")
    if discount_type not in DiscountType.values:
        errors.append(f"discount_type: {DiscountType.values} 중 하나여야 함")

    rate = normalized.get("discount_rate")
    amount = normalized.get("discount_amount")
    if discount_type == DiscountType.RATE:
        try:
            rate = Decimal(str(rate))
            if rate < 0 or rate > 1:
                errors.append("discount_rate: 0 이상 1 이하여야 함")
        except (InvalidOperation, TypeError):
            errors.append("discount_rate: 비율 혜택에는 유효한 할인율이 필요함")
        if amount not in (None, ""):
            errors.append("discount_amount: 비율 혜택에는 사용할 수 없음")
        normalized["discount_rate"] = rate
        normalized["discount_amount"] = None
    elif discount_type == DiscountType.AMOUNT:
        if rate not in (None, ""):
            errors.append("discount_rate: 정액 혜택에는 사용할 수 없음")
        normalized["discount_rate"] = None
        normalized["discount_amount"] = _non_negative_integer(
            amount,
            "discount_amount",
            errors,
        )

    for field_name in (
        "minimum_transaction_amount",
        "maximum_transaction_amount",
        "per_transaction_limit",
        "daily_benefit_limit",
        "daily_usage_limit",
        "monthly_usage_limit",
        "estimated_monthly_uses",
        "category_monthly_limit",
    ):
        normalized[field_name] = _non_negative_integer(
            normalized.get(field_name),
            field_name,
            errors,
            allow_none=field_name != "minimum_transaction_amount",
        )
    if (
        normalized["maximum_transaction_amount"] is not None
        and normalized["maximum_transaction_amount"]
        <= normalized["minimum_transaction_amount"]
    ):
        errors.append(
            "maximum_transaction_amount: minimum_transaction_amount보다 커야 함"
        )

    channel = normalized.get("channel", "all")
    if channel not in SUPPORTED_CHANNELS:
        errors.append(f"channel: {SUPPORTED_CHANNELS} 중 하나여야 함")
    for field_name in ("start_hour", "end_hour"):
        normalized[field_name] = _non_negative_integer(
            normalized.get(field_name),
            field_name,
            errors,
            allow_none=True,
        )
        if (
            normalized[field_name] is not None
            and normalized[field_name] > 24
        ):
            errors.append(f"{field_name}: 0 이상 24 이하여야 함")
    if (
        normalized["start_hour"] is not None
        and normalized["end_hour"] is not None
        and normalized["start_hour"] >= normalized["end_hour"]
    ):
        errors.append("end_hour: start_hour보다 커야 함")

    unsupported = set(normalized.get("unsupported_conditions") or [])
    raw_text = normalized.get("raw_text") or ""
    if (
        normalized.get("monthly_usage_limit") is None
        and re.search(r"최대\s*\d+\s*회", raw_text)
    ):
        unsupported.add("usage_limit_mapping")
    if normalized.get("merchant_scope"):
        unsupported.discard("merchant_scope")
    if normalized.get("exclusion_text"):
        unsupported.add("exclusion_text")
    unsupported &= UNSUPPORTED_CONDITION_FIELDS
    normalized["unsupported_conditions"] = sorted(unsupported)
    review_reasons.extend(
        f"{condition}: 현재 계산 코어에서 자동 적용하지 않음"
        for condition in normalized["unsupported_conditions"]
    )

    if not normalized.get("raw_text"):
        errors.append("raw_text: 원문이 필요함")

    status = (
        ParseStatus.INVALID
        if errors
        else ParseStatus.REVIEW_REQUIRED
        if review_reasons
        else ParseStatus.ACTIVE
    )
    normalized["parse_status"] = status
    return ValidationResult(
        is_valid=not errors,
        parse_status=status,
        normalized_data=normalized,
        errors=errors,
        review_reasons=review_reasons,
    )


def validate_card_product(card):
    errors = []
    review_reasons = []
    normalized = dict(card)

    for field_name in (
        "external_id",
        "issuer",
        "provider",
        "source_channel",
        "name",
        "source_url",
        "raw_text",
    ):
        if not normalized.get(field_name):
            errors.append(f"{field_name}: 필수값")

    if normalized.get("card_type") not in CardType.values:
        errors.append(f"card_type: {CardType.values} 중 하나여야 함")
    normalized_name = (normalized.get("name") or "").casefold()
    if (
        normalized.get("card_type") == CardType.CREDIT
        and ("체크" in normalized_name or "check" in normalized_name)
    ):
        errors.append("card_type: 카드명의 체크카드 표기와 충돌함")

    normalized["annual_fee"] = _non_negative_integer(
        normalized.get("annual_fee"),
        "annual_fee",
        errors,
        allow_none=True,
    )
    normalized["previous_month_requirement"] = _non_negative_integer(
        normalized.get("previous_month_requirement"),
        "previous_month_requirement",
        errors,
    )
    normalized["monthly_discount_limit"] = _non_negative_integer(
        normalized.get("monthly_discount_limit"),
        "monthly_discount_limit",
        errors,
        allow_none=True,
    )

    normalized_benefits = []
    for index, benefit in enumerate(normalized.get("benefits") or []):
        result = validate_benefit_rule(benefit)
        normalized_benefits.append(result.normalized_data)
        errors.extend(f"benefits[{index}].{error}" for error in result.errors)
        review_reasons.extend(result.review_reasons)
    normalized["benefits"] = normalized_benefits

    normalized_tiers = []
    for index, tier in enumerate(normalized.get("benefit_tiers") or []):
        result = validate_benefit_tier(tier)
        normalized_tiers.append(result.normalized_data)
        errors.extend(f"benefit_tiers[{index}].{error}" for error in result.errors)
    normalized["benefit_tiers"] = normalized_tiers

    normalized_service_tiers = []
    for index, tier in enumerate(normalized.get("service_limit_tiers") or []):
        result = validate_service_limit_tier(tier)
        normalized_service_tiers.append(result.normalized_data)
        errors.extend(
            f"service_limit_tiers[{index}].{error}" for error in result.errors
        )
    normalized["service_limit_tiers"] = normalized_service_tiers

    if not normalized_benefits:
        review_reasons.append("구조화된 혜택 규칙이 없음")
    if normalized["annual_fee"] is None:
        review_reasons.append("연회비 미확인")

    status = (
        ParseStatus.INVALID
        if errors
        else ParseStatus.REVIEW_REQUIRED
        if review_reasons
        else ParseStatus.ACTIVE
    )
    normalized["parse_status"] = status
    return ValidationResult(
        is_valid=not errors,
        parse_status=status,
        normalized_data=normalized,
        errors=errors,
        review_reasons=sorted(set(review_reasons)),
    )
