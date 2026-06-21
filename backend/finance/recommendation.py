import re
from math import tanh


CATEGORY_LABELS = {
    "cafe": "카페",
    "convenience": "편의점",
    "food": "음식점",
    "dining": "외식",
    "delivery": "배달",
    "mart": "마트",
    "shopping": "쇼핑",
    "etc": "기타",
}

DEFAULT_INFRASTRUCTURE = {
    "cafe": 8,
    "convenience": 12,
    "food": 9,
    "dining": 9,
    "delivery": 0,
    "mart": 1,
}
DEFAULT_COHORT_SPENDING = {
    "cafe": 102000,
    "convenience": 58000,
    "dining": 130000,
    "delivery": 53000,
    "mart": 89000,
    "shopping": 44000,
    "etc": 0,
}
OWNED_CARD_BADGE = "보유중인 카드"


def calculate_store_weight(store_count):
    return tanh(max(int(store_count or 0), 0) / 2)


def _to_number(value, default=0):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _benefit_rules_for(card):
    benefits = card.get("benefits")
    if benefits:
        return benefits

    return [
        {
            "category": category,
            "discount_type": "rate",
            "discount_rate": card.get("discount_rate", 0),
            "category_monthly_limit": None,
        }
        for category in card.get("focus", [])
    ]


def resolve_spending_profile(spending=None, spending_source=None, fallback_spending=None):
    if spending:
        amounts = {key: _to_number(value, 0) for key, value in spending.items()}
        if "food" in amounts and "dining" not in amounts:
            amounts["dining"] = amounts["food"]
        if "dining" in amounts and "food" not in amounts:
            amounts["food"] = amounts["dining"]
        return {
            "amounts": amounts,
            "source": spending_source or "user",
            "is_cold_start": False,
        }

    fallback = dict(fallback_spending or DEFAULT_COHORT_SPENDING)
    if "dining" in fallback and "food" not in fallback:
        fallback["food"] = fallback["dining"]
    return {
        "amounts": {key: _to_number(value, 0) for key, value in fallback.items()},
        "source": spending_source or "cohort_default",
        "is_cold_start": True,
    }


def _transaction_benefit(rule, amount):
    minimum_amount = _to_number(rule.get("minimum_transaction_amount"), 0)
    if amount < minimum_amount:
        return 0
    maximum_amount = rule.get("maximum_transaction_amount")
    if (
        maximum_amount not in (None, "")
        and amount >= _to_number(maximum_amount, 0)
    ):
        return 0

    if rule.get("discount_type", "rate") == "amount":
        benefit = _to_number(rule.get("discount_amount"), 0)
    else:
        benefit = amount * _to_number(rule.get("discount_rate"), 0)

    per_transaction_limit = rule.get("per_transaction_limit")
    if per_transaction_limit not in (None, ""):
        benefit = min(benefit, _to_number(per_transaction_limit, 0))
    return benefit


def _normalize_merchant_name(value):
    return re.sub(r"[^0-9a-z가-힣]", "", str(value or "").casefold())


def _matches_merchant_scope(merchant_name, merchant_scope):
    normalized_name = _normalize_merchant_name(merchant_name)
    if not normalized_name:
        return False
    return any(
        normalized_scope
        and normalized_scope in normalized_name
        for normalized_scope in (
            _normalize_merchant_name(item) for item in merchant_scope or []
        )
    )


def _transaction_hour(value):
    match = re.match(r"^(\d{1,2}):(\d{2})", str(value or ""))
    if not match:
        return None
    hour, minute = map(int, match.groups())
    if hour > 23 or minute > 59:
        return None
    return hour + minute / 60


def _category_benefit(rule, spending, transactions=None):
    category = rule.get("category")
    transaction_categories = {category}
    if category == "dining":
        transaction_categories.add("food")
    elif category == "food":
        transaction_categories.add("dining")
    merchant_scope = rule.get("merchant_scope") or []
    required_channel = rule.get("channel", "all")
    start_hour = rule.get("start_hour")
    end_hour = rule.get("end_hour")
    category_transactions = [
        item
        for item in (transactions or [])
        if item.get("category") in transaction_categories
        and _to_number(item.get("amount"), 0) > 0
    ]
    channel_transactions = [
        item
        for item in category_transactions
        if required_channel == "all"
        or item.get("channel") == required_channel
    ]
    time_transactions = [
        item
        for item in channel_transactions
        if (
            start_hour in (None, "")
            and end_hour in (None, "")
        )
        or (
            _transaction_hour(item.get("transaction_time")) is not None
            and _to_number(start_hour, 0)
            <= _transaction_hour(item.get("transaction_time"))
            < _to_number(end_hour, 24)
        )
    ]
    scoped_transactions = (
        [
            item
            for item in time_transactions
            if _matches_merchant_scope(item.get("merchant_name"), merchant_scope)
        ]
        if merchant_scope
        else time_transactions
    )
    eligible_category_transactions = [
        item
        for item in scoped_transactions
        if _to_number(item.get("amount"), 0)
        >= _to_number(rule.get("minimum_transaction_amount"), 0)
        and (
            rule.get("maximum_transaction_amount") in (None, "")
            or _to_number(item.get("amount"), 0)
            < _to_number(rule.get("maximum_transaction_amount"), 0)
        )
    ]
    monthly_usage_limit = int(_to_number(rule.get("monthly_usage_limit"), 0))
    daily_usage_limit = int(_to_number(rule.get("daily_usage_limit"), 0))
    exclusion_reason = None
    daily_benefit_limit = rule.get("daily_benefit_limit")

    if (
        (start_hour not in (None, "") or end_hour not in (None, ""))
        and transactions
        and not any(item.get("transaction_time") for item in category_transactions)
    ):
        raw_benefit = 0
        calculation_mode = "time_unavailable"
        transaction_count = 0
        exclusion_reason = "시간대 조건 계산을 위한 거래시각이 필요함"
    elif required_channel != "all" and transactions and not any(
        item.get("channel") for item in category_transactions
    ):
        raw_benefit = 0
        calculation_mode = "channel_unavailable"
        transaction_count = 0
        exclusion_reason = "온라인·오프라인 채널 정보가 필요함"
    elif merchant_scope and not transactions:
        raw_benefit = 0
        calculation_mode = "merchant_scope_unavailable"
        transaction_count = 0
        exclusion_reason = "가맹점명이 포함된 거래 데이터가 필요함"
    elif merchant_scope or eligible_category_transactions:
        eligible_transactions = eligible_category_transactions
        if daily_usage_limit and any(
            not item.get("transaction_date") for item in eligible_transactions
        ):
            eligible_transactions = []
            exclusion_reason = "일 횟수 계산을 위한 거래일자가 필요함"
        elif daily_usage_limit:
            daily_counts = {}
            limited_transactions = []
            for item in eligible_transactions:
                transaction_date = item.get("transaction_date")
                if not transaction_date:
                    continue
                count = daily_counts.get(transaction_date, 0)
                if count >= daily_usage_limit:
                    continue
                daily_counts[transaction_date] = count + 1
                limited_transactions.append(item)
            eligible_transactions = limited_transactions
        eligible_transactions = eligible_transactions[:monthly_usage_limit or None]
        if (
            daily_benefit_limit not in (None, "")
            and any(not item.get("transaction_date") for item in eligible_transactions)
        ):
            raw_benefit = 0
            transaction_count = 0
            exclusion_reason = "일 한도 계산을 위한 거래일자가 필요함"
        elif daily_benefit_limit not in (None, ""):
            daily_benefits = {}
            for item in eligible_transactions:
                transaction_date = str(item["transaction_date"])
                benefit = _transaction_benefit(
                    rule,
                    _to_number(item.get("amount"), 0),
                )
                daily_benefits[transaction_date] = (
                    daily_benefits.get(transaction_date, 0) + benefit
                )
            raw_benefit = (
                sum(daily_benefits.values())
                if rule.get("benefit_group")
                else sum(
                    min(benefit, _to_number(daily_benefit_limit, 0))
                    for benefit in daily_benefits.values()
                )
            )
            transaction_count = len(eligible_transactions)
        else:
            raw_benefit = sum(
                _transaction_benefit(rule, _to_number(item.get("amount"), 0))
                for item in eligible_transactions
            )
            transaction_count = len(eligible_transactions)
        calculation_mode = "transaction"
        if (
            (start_hour not in (None, "") or end_hour not in (None, ""))
            and category_transactions
            and not time_transactions
        ):
            exclusion_reason = "혜택 적용 시간대와 일치하는 거래가 없음"
        elif merchant_scope and not scoped_transactions:
            exclusion_reason = "혜택 대상 가맹점과 일치하는 거래가 없음"
    else:
        spending_amount = _to_number(spending.get(category), 0)
        if rule.get("discount_type", "rate") == "amount":
            estimated_uses = int(_to_number(rule.get("estimated_monthly_uses"), 1))
            if monthly_usage_limit:
                estimated_uses = min(estimated_uses, monthly_usage_limit)
            raw_benefit = _to_number(rule.get("discount_amount"), 0) * estimated_uses
            transaction_count = estimated_uses
        else:
            raw_benefit = spending_amount * _to_number(rule.get("discount_rate"), 0)
            per_transaction_limit = rule.get("per_transaction_limit")
            if per_transaction_limit not in (None, ""):
                estimated_uses = int(_to_number(rule.get("estimated_monthly_uses"), 1))
                if monthly_usage_limit:
                    estimated_uses = min(estimated_uses, monthly_usage_limit)
                raw_benefit = min(
                    raw_benefit,
                    _to_number(per_transaction_limit, 0) * estimated_uses,
                )
                transaction_count = estimated_uses
            else:
                transaction_count = 0
        calculation_mode = "aggregate_estimate"

    category_limit = rule.get("category_monthly_limit")
    final_benefit = raw_benefit
    if category_limit not in (None, ""):
        final_benefit = min(final_benefit, _to_number(category_limit, 0))

    return {
        "category": category,
        "benefit_group": rule.get("benefit_group", ""),
        "category_label": CATEGORY_LABELS.get(category, category),
        "spending": int(_to_number(spending.get(category), 0)),
        "discount_type": rule.get("discount_type", "rate"),
        "discount_rate": _to_number(rule.get("discount_rate"), 0),
        "discount_amount": int(_to_number(rule.get("discount_amount"), 0)),
        "raw_benefit": int(raw_benefit),
        "category_monthly_limit": (
            int(_to_number(category_limit, 0)) if category_limit not in (None, "") else None
        ),
        "final_benefit": int(final_benefit),
        "calculation_mode": calculation_mode,
        "transaction_count": transaction_count,
        "merchant_scope": merchant_scope,
        "channel": required_channel,
        "start_hour": (
            int(_to_number(start_hour, 0))
            if start_hour not in (None, "")
            else None
        ),
        "end_hour": (
            int(_to_number(end_hour, 0))
            if end_hour not in (None, "")
            else None
        ),
        "matched_transaction_count": len(scoped_transactions),
        "excluded_transaction_count": (
            len(category_transactions) - transaction_count
            if transactions
            else 0
        ),
        "exclusion_reason": exclusion_reason,
        "daily_benefit_limit": (
            int(_to_number(daily_benefit_limit, 0))
            if daily_benefit_limit not in (None, "")
            else None
        ),
        "daily_benefits": (
            {key: int(value) for key, value in daily_benefits.items()}
            if daily_benefit_limit not in (None, "")
            and "daily_benefits" in locals()
            else {}
        ),
    }


def calculate_local_fit_score(benefits, spending, infrastructure):
    categories = {rule.get("category") for rule in benefits if rule.get("category")}
    if not categories:
        return 0

    category_spending = {category: _to_number(spending.get(category), 0) for category in categories}
    total_spending = sum(category_spending.values())
    if total_spending:
        weights = {
            category: amount / total_spending for category, amount in category_spending.items()
        }
    else:
        equal_weight = 1 / len(categories)
        weights = {category: equal_weight for category in categories}

    weighted_fit = sum(
        calculate_store_weight(infrastructure.get(category, 0)) * weights[category]
        for category in categories
    )
    return round(weighted_fit * 100, 1)


def select_benefit_tier(benefit_tiers, previous_month_spending, scope="card_total"):
    spending = _to_number(previous_month_spending, 0)
    matching = []
    for tier in benefit_tiers or []:
        if tier.get("scope", "card_total") != scope:
            continue
        minimum = _to_number(tier.get("minimum_spending"), 0)
        maximum = tier.get("maximum_spending")
        if spending < minimum:
            continue
        if maximum not in (None, "") and spending >= _to_number(maximum, 0):
            continue
        matching.append(tier)
    if not matching:
        return None
    return max(matching, key=lambda item: _to_number(item.get("minimum_spending"), 0))


def select_service_limit_tier(
    service_limit_tiers,
    previous_month_spending,
    benefit_group,
):
    spending = _to_number(previous_month_spending, 0)
    matching = []
    for tier in service_limit_tiers or []:
        if tier.get("benefit_group") != benefit_group:
            continue
        minimum = _to_number(tier.get("minimum_spending"), 0)
        maximum = tier.get("maximum_spending")
        if spending < minimum:
            continue
        if maximum not in (None, "") and spending >= _to_number(maximum, 0):
            continue
        matching.append(tier)
    if not matching:
        return None
    return max(matching, key=lambda item: _to_number(item.get("minimum_spending"), 0))


def apply_service_group_limits(
    breakdown,
    service_limit_tiers,
    previous_month_spending,
):
    selected_tiers = {}
    groups = {
        item["benefit_group"]
        for item in breakdown
        if item.get("benefit_group")
    }
    for group in groups:
        configured_tiers = [
            item
            for item in service_limit_tiers or []
            if item.get("benefit_group") == group
        ]
        tier = select_service_limit_tier(
            service_limit_tiers,
            previous_month_spending,
            group,
        )
        if not tier:
            if configured_tiers:
                for item in breakdown:
                    if item.get("benefit_group") == group:
                        item["final_benefit"] = 0
                        item["service_group_status"] = "실적 구간 미충족"
            continue

        group_items = [
            item for item in breakdown if item.get("benefit_group") == group
        ]
        discount_limit = tier.get("monthly_discount_limit")
        if discount_limit in (None, ""):
            spending_limit = tier.get("monthly_spending_limit")
            rates = {
                item["discount_rate"]
                for item in group_items
                if item["discount_type"] == "rate"
            }
            if spending_limit not in (None, "") and len(rates) == 1:
                discount_limit = _to_number(spending_limit, 0) * rates.pop()

        if discount_limit not in (None, ""):
            effective_limit = int(_to_number(discount_limit, 0))
            daily_limits = {
                item["daily_benefit_limit"]
                for item in group_items
                if item.get("daily_benefit_limit") is not None
            }
            if len(daily_limits) == 1:
                daily_limit = daily_limits.pop()
                grouped_daily_benefits = {}
                for item in group_items:
                    for transaction_date, benefit in item.get(
                        "daily_benefits", {}
                    ).items():
                        grouped_daily_benefits[transaction_date] = (
                            grouped_daily_benefits.get(transaction_date, 0)
                            + benefit
                        )
                if grouped_daily_benefits:
                    effective_limit = min(
                        effective_limit,
                        sum(
                            min(benefit, daily_limit)
                            for benefit in grouped_daily_benefits.values()
                        ),
                    )
            remaining = effective_limit
            for item in group_items:
                item["final_benefit"] = min(item["final_benefit"], remaining)
                remaining -= item["final_benefit"]
                item["service_group_limit"] = int(
                    _to_number(discount_limit, 0)
                )

        selected_tiers[group] = {
            "benefit_group": group,
            "minimum_spending": int(
                _to_number(tier.get("minimum_spending"), 0)
            ),
            "maximum_spending": (
                int(_to_number(tier.get("maximum_spending"), 0))
                if tier.get("maximum_spending") not in (None, "")
                else None
            ),
            "monthly_spending_limit": (
                int(_to_number(tier.get("monthly_spending_limit"), 0))
                if tier.get("monthly_spending_limit") not in (None, "")
                else None
            ),
            "monthly_discount_limit": (
                int(_to_number(discount_limit, 0))
                if discount_limit not in (None, "")
                else None
            ),
            "monthly_usage_limit": (
                int(_to_number(tier.get("monthly_usage_limit"), 0))
                if tier.get("monthly_usage_limit") not in (None, "")
                else None
            ),
        }
    return selected_tiers


def calculate_card_recommendation(
    card,
    spending=None,
    infrastructure=None,
    previous_month_spending=0,
    owned_card_ids=None,
    transactions=None,
    spending_source=None,
    fallback_spending=None,
):
    infrastructure = infrastructure or DEFAULT_INFRASTRUCTURE
    owned_card_ids = set(owned_card_ids or [])
    spending_profile = resolve_spending_profile(
        spending=spending,
        spending_source=spending_source,
        fallback_spending=fallback_spending,
    )
    resolved_spending = spending_profile["amounts"]

    previous_month_requirement = int(_to_number(card.get("previous_month_requirement"), 0))
    selected_tier = select_benefit_tier(
        card.get("benefit_tiers"),
        previous_month_spending,
    )
    tier_limit = selected_tier.get("monthly_discount_limit") if selected_tier else None
    monthly_discount_limit = int(
        _to_number(
            tier_limit
            if tier_limit not in (None, "")
            else card.get("monthly_discount_limit", card.get("max_discount_limit")),
            0,
        )
    )
    annual_fee_raw = card.get("annual_fee")
    annual_fee = (
        int(_to_number(annual_fee_raw, 0))
        if annual_fee_raw not in (None, "")
        else None
    )
    monthly_annual_fee = round(annual_fee / 12) if annual_fee is not None else None
    is_eligible = _to_number(previous_month_spending, 0) >= previous_month_requirement

    benefits = _benefit_rules_for(card)
    breakdown = [
        _category_benefit(rule, resolved_spending, transactions=transactions) for rule in benefits
    ]
    selected_service_limit_tiers = apply_service_group_limits(
        breakdown,
        card.get("service_limit_tiers"),
        previous_month_spending,
    )
    uncapped_benefit = sum(item["final_benefit"] for item in breakdown)
    estimated_gross_benefit = (
        min(uncapped_benefit, monthly_discount_limit)
        if monthly_discount_limit
        else uncapped_benefit
    )
    if not is_eligible:
        estimated_gross_benefit = 0

    estimated_net_value = (
        estimated_gross_benefit - monthly_annual_fee
        if monthly_annual_fee is not None
        else None
    )
    local_fit_score = calculate_local_fit_score(
        benefits=benefits,
        spending=resolved_spending,
        infrastructure=infrastructure,
    )
    is_owned = card.get("id") in owned_card_ids

    result = {
        "id": card.get("id"),
        "name": card.get("name"),
        "issuer": card.get("issuer"),
        "image_url": card.get("image_url", ""),
        "focus": [CATEGORY_LABELS.get(item, item) for item in card.get("focus", [])],
        "estimated_savings": int(estimated_gross_benefit),
        "estimated_gross_benefit": int(estimated_gross_benefit),
        "estimated_net_value": (
            int(estimated_net_value) if estimated_net_value is not None else None
        ),
        "annual_fee": annual_fee,
        "monthly_annual_fee": monthly_annual_fee,
        "annual_fee_is_known": annual_fee is not None,
        "selected_benefit_tier": (
            {
                "scope": selected_tier.get("scope", "card_total"),
                "minimum_spending": int(
                    _to_number(selected_tier.get("minimum_spending"), 0)
                ),
                "maximum_spending": (
                    int(_to_number(selected_tier.get("maximum_spending"), 0))
                    if selected_tier.get("maximum_spending") not in (None, "")
                    else None
                ),
                "monthly_discount_limit": monthly_discount_limit,
            }
            if selected_tier
            else None
        ),
        "selected_service_limit_tiers": selected_service_limit_tiers,
        "local_fit_score": local_fit_score,
        "seul_score": 0,
        "monthly_discount_limit": monthly_discount_limit,
        "previous_month_requirement": previous_month_requirement,
        "is_eligible": is_eligible,
        "is_recommendation_ready": is_eligible and annual_fee is not None,
        "is_owned": is_owned,
        "badge": OWNED_CARD_BADGE if is_owned else "",
        "spending_profile": {
            "source": spending_profile["source"],
            "is_cold_start": spending_profile["is_cold_start"],
            "amounts": {key: int(value) for key, value in resolved_spending.items()},
        },
        "uncapped_gross_benefit": int(uncapped_benefit),
        "applied_total_monthly_limit": monthly_discount_limit or None,
        "calculation_breakdown": breakdown,
    }
    if not is_eligible:
        result["eligibility_status"] = "전월 실적 미충족"
    if annual_fee is None:
        result["net_value_status"] = "연회비 미확인"

    return result


def _apply_seul_scores(recommendations):
    eligible_net_values = [
        max(item["estimated_net_value"], 0)
        for item in recommendations
        if item["is_recommendation_ready"]
    ]
    max_net_value = max(eligible_net_values, default=0)
    max_local_fit = max(
        (item["local_fit_score"] for item in recommendations if item["is_recommendation_ready"]),
        default=0,
    )

    for item in recommendations:
        if not item["is_recommendation_ready"] or max_net_value == 0:
            item["seul_score"] = 0
            item["ranking_score"] = 0
            continue

        net_value_score = max(item["estimated_net_value"], 0) / max_net_value * 100
        local_fit_score = (
            item["local_fit_score"] / max_local_fit * 100 if max_local_fit else 0
        )
        item["ranking_score"] = round(net_value_score * 0.6 + local_fit_score * 0.4, 1)
        item["seul_score"] = item["ranking_score"]


def rank_card_recommendations(
    cards,
    spending=None,
    infrastructure=None,
    previous_month_spending=0,
    owned_card_ids=None,
    transactions=None,
    spending_source=None,
    fallback_spending=None,
):
    recommendations = [
        calculate_card_recommendation(
            card=card,
            spending=spending,
            infrastructure=infrastructure,
            previous_month_spending=previous_month_spending,
            owned_card_ids=owned_card_ids,
            transactions=transactions,
            spending_source=spending_source,
            fallback_spending=fallback_spending,
        )
        for card in cards
    ]
    _apply_seul_scores(recommendations)
    return sorted(
        recommendations,
        key=lambda item: (
            item["is_eligible"],
            item["is_recommendation_ready"],
            item.get("ranking_score", 0),
            item["local_fit_score"],
            item["estimated_net_value"]
            if item["estimated_net_value"] is not None
            else float("-inf"),
            item["estimated_gross_benefit"],
        ),
        reverse=True,
    )
