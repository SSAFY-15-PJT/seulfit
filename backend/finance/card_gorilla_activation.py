from dataclasses import dataclass
import re

from .models import ParseStatus


COMPLEX_PATTERNS = {
    "choice_option": ("선택", "택 1", "옵션"),
    "tiered_limit": (
        "이용금액대별",
        "실적 구간",
        "전월실적 30만원~",
        "전월실적 50만원 ~",
    ),
    "time_or_day": (
        "오후",
        "오전",
        "시간",
        "주중",
        "주말",
        "평일",
        "요일",
    ),
    "variable_rate": ("최대 ", "~", "브랜드별", "적립율 구분"),
}

DISPLAY_ONLY_CONDITIONS = {
    "choice_option",
    "payment_method_condition",
    "time_or_day",
}


@dataclass(frozen=True)
class CardGorillaActivationDecision:
    card_id: int
    card_name: str
    activatable_benefit_ids: list[int]
    blocked_benefits: dict[int, list[str]]
    card_blockers: list[str]

    @property
    def can_activate(self):
        return not self.card_blockers and bool(self.activatable_benefit_ids)


def evaluate_benefit_for_activation(benefit):
    blockers = []
    text = benefit.raw_text or ""

    if benefit.discount_type == "rate" and benefit.discount_rate is None:
        blockers.append("missing_discount_rate")
    if benefit.discount_type == "amount" and benefit.discount_amount is None:
        blockers.append("missing_discount_amount")

    for reason, patterns in COMPLEX_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            blockers.append(reason)

    unsupported = set(benefit.unsupported_conditions or [])
    if "mixed_channel_mapping" in unsupported:
        blockers.append("channel_unparsed")
    if "payment_method_condition" in unsupported:
        blockers.append("payment_method_condition")

    has_monthly_limit_text = bool(
        re.search(
            r"(?:월\s*(?:할인|적립|캐시백)?\s*한도|월\s*최대\s*"
            r"[\d,.]+\s*(?:만|천)?\s*원)",
            text,
        )
    )
    if has_monthly_limit_text and benefit.category_monthly_limit is None:
        blockers.append("monthly_limit_unparsed")

    if re.search(r"(?:건당|1회)\s*[\d,.]+\s*(?:만|천)?\s*원\s*이상", text):
        if benefit.minimum_transaction_amount == 0:
            blockers.append("minimum_transaction_unparsed")
    if re.search(r"(?:월|매월)\s*\d+\s*회", text):
        if benefit.monthly_usage_limit is None:
            blockers.append("monthly_usage_unparsed")
    if re.search(r"(?:일|하루)\s*\d+\s*회", text):
        if benefit.daily_usage_limit is None:
            blockers.append("daily_usage_unparsed")
    if any(pattern in text for pattern in ("통합", "공유 한도")):
        card_monthly_limit = getattr(
            getattr(benefit, "card", None),
            "monthly_discount_limit",
            None,
        )
        if (
            benefit.category_monthly_limit is None
            and card_monthly_limit is None
        ):
            blockers.append("shared_limit")
    if benefit.category == "delivery" and not benefit.merchant_scope:
        blockers.append("merchant_scope_required")
    if benefit.category in {"cafe", "convenience"}:
        has_generic_scope = any(
            phrase in text
            for phrase in (
                "전 가맹점",
                "전가맹점",
                "국내 가맹점",
                "국내가맹점",
                "국내 전 가맹점",
                "국내전가맹점",
                "국내/외 전가맹점",
                "국내/외 모든 가맹점",
                "국내외 모든 가맹점",
                "국내외 가맹점",
                "모든 가맹점",
                "커피 업종",
                "카페 업종",
                "커피전문점 업종",
                "커피음료전문점 업종",
                "커피/음료전문업종",
                "커피/음료전문점 업종",
                "편의점 업종",
            )
        )
        if not has_generic_scope and not benefit.merchant_scope:
            blockers.append("merchant_scope_required")

    return sorted(set(blockers))


def collect_display_only_conditions(benefit):
    text = benefit.raw_text or ""
    conditions = set(benefit.unsupported_conditions or [])
    if any(pattern in text for pattern in COMPLEX_PATTERNS["choice_option"]):
        conditions.add("choice_option")
    if any(pattern in text for pattern in COMPLEX_PATTERNS["time_or_day"]):
        conditions.add("time_or_day")
    if "payment_method_condition" in conditions or any(
        pattern in text
        for pattern in (
            "바코드 결제",
            "간편결제 제외",
            "간편 결제로 진행하는 경우 할인 적용 불가",
            "특정 결제수단",
            "배민페이",
            "사이렌오더",
            "삼성페이 결제",
        )
    ):
        conditions.add("payment_method_condition")
    return sorted(conditions & DISPLAY_ONLY_CONDITIONS)


def evaluate_card_gorilla_activation(card):
    card_blockers = []
    if card.source_channel != "card_gorilla":
        card_blockers.append("not_card_gorilla")
    if card.annual_fee is None:
        card_blockers.append("annual_fee_missing")
    if card.validation_errors:
        card_blockers.append("card_validation_errors")

    activatable = []
    blocked = {}
    for benefit in card.benefits.all():
        blockers = evaluate_benefit_for_activation(benefit)
        if blockers:
            blocked[benefit.pk] = blockers
        else:
            activatable.append(benefit.pk)

    if not activatable:
        card_blockers.append("no_fully_modeled_benefits")
    return CardGorillaActivationDecision(
        card_id=card.pk,
        card_name=card.name,
        activatable_benefit_ids=activatable,
        blocked_benefits=blocked,
        card_blockers=sorted(set(card_blockers)),
    )


def apply_card_gorilla_activation(card, decision):
    if not decision.can_activate:
        return False

    card.benefits.filter(pk__in=decision.activatable_benefit_ids).update(
        parse_status=ParseStatus.ACTIVE,
        unsupported_conditions=[],
    )
    card.parse_status = ParseStatus.ACTIVE
    card.review_reasons = [
        "일부 복잡한 혜택은 추천 계산에서 제외됨"
    ] if decision.blocked_benefits else []
    card.save(update_fields=["parse_status", "review_reasons", "updated_at"])
    return True
