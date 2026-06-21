from django.test import SimpleTestCase

from finance.recommendation import calculate_card_recommendation, rank_card_recommendations


class RecommendationCoreTests(SimpleTestCase):
    def test_time_and_daily_usage_conditions_filter_transactions(self):
        card = {
            "id": 1,
            "name": "Evening Card",
            "issuer": "Issuer",
            "annual_fee": 0,
            "previous_month_requirement": 0,
            "benefits": [
                {
                    "category": "cafe",
                    "discount_type": "rate",
                    "discount_rate": 0.05,
                    "minimum_transaction_amount": 10000,
                    "per_transaction_limit": 2000,
                    "daily_usage_limit": 1,
                    "monthly_usage_limit": 3,
                    "start_hour": 18,
                    "end_hour": 23,
                    "channel": "offline",
                }
            ],
        }
        transactions = [
            {
                "category": "cafe",
                "amount": 20000,
                "transaction_date": "2026-06-01",
                "transaction_time": "17:59",
                "channel": "offline",
            },
            {
                "category": "cafe",
                "amount": 20000,
                "transaction_date": "2026-06-01",
                "transaction_time": "18:30",
                "channel": "offline",
            },
            {
                "category": "cafe",
                "amount": 20000,
                "transaction_date": "2026-06-01",
                "transaction_time": "20:00",
                "channel": "offline",
            },
            {
                "category": "cafe",
                "amount": 20000,
                "transaction_date": "2026-06-02",
                "transaction_time": "22:59",
                "channel": "offline",
            },
        ]

        result = calculate_card_recommendation(
            card=card,
            spending={"cafe": 80000},
            transactions=transactions,
        )

        self.assertEqual(result["estimated_gross_benefit"], 2000)
        self.assertEqual(
            result["calculation_breakdown"][0]["transaction_count"],
            2,
        )

    def test_time_condition_requires_transaction_time(self):
        card = {
            "id": 1,
            "name": "Evening Card",
            "issuer": "Issuer",
            "annual_fee": 0,
            "previous_month_requirement": 0,
            "benefits": [
                {
                    "category": "cafe",
                    "discount_type": "rate",
                    "discount_rate": 0.05,
                    "start_hour": 18,
                    "end_hour": 23,
                }
            ],
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"cafe": 20000},
            transactions=[{"category": "cafe", "amount": 20000}],
        )

        self.assertEqual(result["estimated_gross_benefit"], 0)
        self.assertEqual(
            result["calculation_breakdown"][0]["exclusion_reason"],
            "시간대 조건 계산을 위한 거래시각이 필요함",
        )

    def test_time_condition_explains_out_of_range_transactions(self):
        card = {
            "id": 1,
            "name": "Evening Card",
            "issuer": "Issuer",
            "annual_fee": 0,
            "previous_month_requirement": 0,
            "benefits": [
                {
                    "category": "convenience",
                    "discount_type": "rate",
                    "discount_rate": 0.05,
                    "merchant_scope": ["CU"],
                    "start_hour": 18,
                    "end_hour": 23,
                }
            ],
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"convenience": 10000},
            transactions=[
                {
                    "category": "convenience",
                    "merchant_name": "CU",
                    "amount": 10000,
                    "transaction_time": "23:00",
                }
            ],
        )

        self.assertEqual(
            result["calculation_breakdown"][0]["exclusion_reason"],
            "혜택 적용 시간대와 일치하는 거래가 없음",
        )

    def test_daily_usage_limit_requires_transaction_date(self):
        card = {
            "id": 1,
            "name": "Daily Usage Card",
            "issuer": "Issuer",
            "annual_fee": 0,
            "previous_month_requirement": 0,
            "benefits": [
                {
                    "category": "cafe",
                    "discount_type": "rate",
                    "discount_rate": 0.05,
                    "daily_usage_limit": 1,
                }
            ],
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"cafe": 20000},
            transactions=[{"category": "cafe", "amount": 20000}],
        )

        self.assertEqual(result["estimated_gross_benefit"], 0)
        self.assertEqual(
            result["calculation_breakdown"][0]["exclusion_reason"],
            "일 횟수 계산을 위한 거래일자가 필요함",
        )
    def test_channel_specific_benefit_requires_matching_channel(self):
        card = {
            "id": 1,
            "name": "Offline Card",
            "issuer": "Issuer",
            "annual_fee": 0,
            "previous_month_requirement": 0,
            "benefits": [
                {
                    "category": "mart",
                    "discount_type": "rate",
                    "discount_rate": 0.1,
                    "merchant_scope": ["이마트"],
                    "channel": "offline",
                }
            ],
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"mart": 100000},
            transactions=[
                {
                    "category": "mart",
                    "merchant_name": "이마트",
                    "amount": 100000,
                    "channel": "online",
                }
            ],
        )

        self.assertEqual(result["estimated_gross_benefit"], 0)

    def test_channel_specific_benefit_rejects_missing_channel(self):
        card = {
            "id": 1,
            "name": "Offline Card",
            "issuer": "Issuer",
            "annual_fee": 0,
            "previous_month_requirement": 0,
            "benefits": [
                {
                    "category": "mart",
                    "discount_type": "rate",
                    "discount_rate": 0.1,
                    "merchant_scope": ["이마트"],
                    "channel": "offline",
                }
            ],
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"mart": 100000},
            transactions=[
                {
                    "category": "mart",
                    "merchant_name": "이마트",
                    "amount": 100000,
                }
            ],
        )

        self.assertEqual(result["estimated_gross_benefit"], 0)
        self.assertEqual(
            result["calculation_breakdown"][0]["exclusion_reason"],
            "온라인·오프라인 채널 정보가 필요함",
        )

    def test_daily_benefit_limit_is_applied_by_transaction_date(self):
        card = {
            "id": 1,
            "name": "Daily Limit Card",
            "issuer": "Issuer",
            "annual_fee": 0,
            "previous_month_requirement": 0,
            "benefits": [
                {
                    "category": "cafe",
                    "discount_type": "rate",
                    "discount_rate": 0.05,
                    "per_transaction_limit": 500,
                    "daily_benefit_limit": 1000,
                }
            ],
        }
        transactions = [
            {"category": "cafe", "amount": 10000, "transaction_date": "2026-06-01"},
            {"category": "cafe", "amount": 10000, "transaction_date": "2026-06-01"},
            {"category": "cafe", "amount": 10000, "transaction_date": "2026-06-01"},
            {"category": "cafe", "amount": 10000, "transaction_date": "2026-06-02"},
        ]

        result = calculate_card_recommendation(
            card=card,
            spending={"cafe": 40000},
            transactions=transactions,
        )

        self.assertEqual(result["estimated_gross_benefit"], 1500)

    def test_daily_benefit_limit_is_shared_across_service_categories(self):
        card = {
            "id": 1,
            "name": "Shared Daily Limit Card",
            "issuer": "Issuer",
            "annual_fee": 0,
            "previous_month_requirement": 0,
            "benefits": [
                {
                    "category": category,
                    "benefit_group": "daily_group",
                    "discount_type": "rate",
                    "discount_rate": 0.05,
                    "per_transaction_limit": 500,
                    "daily_benefit_limit": 1000,
                }
                for category in ("cafe", "convenience", "shopping")
            ],
            "service_limit_tiers": [
                {
                    "benefit_group": "daily_group",
                    "minimum_spending": 0,
                    "maximum_spending": None,
                    "monthly_discount_limit": 5000,
                }
            ],
        }
        transactions = [
            {
                "category": category,
                "amount": 10000,
                "transaction_date": "2026-06-01",
            }
            for category in ("cafe", "convenience", "shopping")
        ]

        result = calculate_card_recommendation(
            card=card,
            spending={
                "cafe": 10000,
                "convenience": 10000,
                "shopping": 10000,
            },
            transactions=transactions,
        )

        self.assertEqual(result["estimated_gross_benefit"], 1000)

    def test_daily_limit_requires_transaction_date(self):
        card = {
            "id": 1,
            "name": "Daily Limit Card",
            "issuer": "Issuer",
            "annual_fee": 0,
            "previous_month_requirement": 0,
            "benefits": [
                {
                    "category": "cafe",
                    "discount_type": "rate",
                    "discount_rate": 0.05,
                    "daily_benefit_limit": 1000,
                }
            ],
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"cafe": 10000},
            transactions=[{"category": "cafe", "amount": 10000}],
        )

        detail = result["calculation_breakdown"][0]
        self.assertEqual(result["estimated_gross_benefit"], 0)
        self.assertEqual(
            detail["exclusion_reason"],
            "일 한도 계산을 위한 거래일자가 필요함",
        )

    def test_transaction_maximum_amount_excludes_upper_bound(self):
        card = {
            "id": 1,
            "name": "Transaction Range Card",
            "issuer": "Issuer",
            "annual_fee": 0,
            "previous_month_requirement": 0,
            "benefits": [
                {
                    "category": "shopping",
                    "discount_type": "amount",
                    "discount_amount": 2500,
                    "maximum_transaction_amount": 30000,
                }
            ],
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"shopping": 50000},
            transactions=[
                {"category": "shopping", "amount": 29999},
                {"category": "shopping", "amount": 30000},
            ],
        )

        self.assertEqual(result["estimated_gross_benefit"], 2500)
        self.assertEqual(
            result["calculation_breakdown"][0]["transaction_count"],
            1,
        )

    def test_shared_service_limit_caps_grouped_categories(self):
        card = {
            "id": 1,
            "name": "Shared Limit Card",
            "issuer": "Issuer",
            "focus": ["cafe", "convenience"],
            "annual_fee": 12000,
            "previous_month_requirement": 300000,
            "benefits": [
                {
                    "category": "cafe",
                    "benefit_group": "life_service",
                    "discount_type": "rate",
                    "discount_rate": 0.05,
                },
                {
                    "category": "convenience",
                    "benefit_group": "life_service",
                    "discount_type": "rate",
                    "discount_rate": 0.05,
                },
            ],
            "service_limit_tiers": [
                {
                    "benefit_group": "life_service",
                    "minimum_spending": 300000,
                    "maximum_spending": 700000,
                    "monthly_spending_limit": 150000,
                    "monthly_discount_limit": 7500,
                    "monthly_usage_limit": None,
                }
            ],
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"cafe": 100000, "convenience": 100000},
            previous_month_spending=500000,
        )

        self.assertEqual(result["estimated_gross_benefit"], 7500)
        self.assertEqual(
            result["selected_service_limit_tiers"]["life_service"][
                "monthly_spending_limit"
            ],
            150000,
        )
        self.assertEqual(result["estimated_net_value"], 6500)

    def test_service_group_benefit_is_zero_below_its_tier_requirement(self):
        card = {
            "id": 1,
            "name": "Tiered Service Card",
            "issuer": "Issuer",
            "annual_fee": 0,
            "previous_month_requirement": 300000,
            "benefits": [
                {
                    "category": "mart",
                    "benefit_group": "mart_service",
                    "discount_type": "rate",
                    "discount_rate": 0.1,
                }
            ],
            "service_limit_tiers": [
                {
                    "benefit_group": "mart_service",
                    "minimum_spending": 500000,
                    "maximum_spending": None,
                    "monthly_discount_limit": 2000,
                }
            ],
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"mart": 100000},
            previous_month_spending=400000,
        )

        detail = result["calculation_breakdown"][0]
        self.assertEqual(result["estimated_gross_benefit"], 0)
        self.assertEqual(detail["service_group_status"], "실적 구간 미충족")

    def test_spending_tier_selects_total_monthly_limit(self):
        card = {
            "id": 1,
            "name": "Tier Card",
            "issuer": "Issuer",
            "focus": ["cafe"],
            "discount_rate": 0.5,
            "annual_fee": 12000,
            "previous_month_requirement": 400000,
            "monthly_discount_limit": None,
            "benefit_tiers": [
                {
                    "scope": "card_total",
                    "minimum_spending": 400000,
                    "maximum_spending": 800000,
                    "monthly_discount_limit": 10000,
                },
                {
                    "scope": "card_total",
                    "minimum_spending": 800000,
                    "maximum_spending": None,
                    "monthly_discount_limit": 20000,
                },
            ],
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"cafe": 100000},
            previous_month_spending=900000,
        )

        self.assertEqual(result["estimated_gross_benefit"], 20000)
        self.assertEqual(result["selected_benefit_tier"]["minimum_spending"], 800000)
        self.assertEqual(result["estimated_net_value"], 19000)

    def test_unknown_annual_fee_keeps_net_value_unconfirmed(self):
        card = {
            "id": 1,
            "name": "Unknown Fee Card",
            "issuer": "Issuer",
            "focus": ["cafe"],
            "discount_rate": 0.1,
            "annual_fee": None,
            "monthly_discount_limit": 30000,
            "previous_month_requirement": 0,
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"cafe": 100000},
        )

        self.assertEqual(result["estimated_gross_benefit"], 10000)
        self.assertIsNone(result["estimated_net_value"])
        self.assertFalse(result["annual_fee_is_known"])
        self.assertFalse(result["is_recommendation_ready"])
        self.assertEqual(result["net_value_status"], "연회비 미확인")

    def test_unknown_annual_fee_card_ranks_after_ready_card(self):
        cards = [
            {
                "id": 1,
                "name": "Unknown Fee",
                "issuer": "Issuer",
                "focus": ["cafe"],
                "discount_rate": 0.2,
                "annual_fee": None,
                "monthly_discount_limit": 30000,
                "previous_month_requirement": 0,
            },
            {
                "id": 2,
                "name": "Ready",
                "issuer": "Issuer",
                "focus": ["cafe"],
                "discount_rate": 0.1,
                "annual_fee": 0,
                "monthly_discount_limit": 30000,
                "previous_month_requirement": 0,
            },
        ]

        results = rank_card_recommendations(
            cards=cards,
            spending={"cafe": 100000},
        )

        self.assertEqual(results[0]["id"], 2)
        self.assertTrue(results[0]["is_recommendation_ready"])

    def test_category_and_total_limits_cap_gross_benefit(self):
        card = {
            "id": 1,
            "name": "Limit Card",
            "issuer": "Issuer",
            "focus": ["cafe", "food"],
            "annual_fee": 0,
            "monthly_discount_limit": 15000,
            "previous_month_requirement": 0,
            "benefits": [
                {
                    "category": "cafe",
                    "discount_type": "rate",
                    "discount_rate": 0.5,
                    "category_monthly_limit": 10000,
                },
                {
                    "category": "food",
                    "discount_type": "rate",
                    "discount_rate": 0.5,
                    "category_monthly_limit": 10000,
                },
            ],
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"cafe": 100000, "food": 100000},
            infrastructure={"cafe": 20, "food": 20},
        )

        self.assertEqual(result["calculation_breakdown"][0]["final_benefit"], 10000)
        self.assertEqual(result["calculation_breakdown"][1]["final_benefit"], 10000)
        self.assertEqual(result["estimated_gross_benefit"], 15000)

    def test_store_count_changes_local_fit_but_not_benefit(self):
        card = {
            "id": 1,
            "name": "Local Card",
            "issuer": "Issuer",
            "focus": ["cafe"],
            "discount_rate": 0.1,
            "annual_fee": 0,
            "monthly_discount_limit": 30000,
            "previous_month_requirement": 0,
        }

        low_density = calculate_card_recommendation(
            card=card,
            spending={"cafe": 100000},
            infrastructure={"cafe": 1},
        )
        high_density = calculate_card_recommendation(
            card=card,
            spending={"cafe": 100000},
            infrastructure={"cafe": 20},
        )

        self.assertEqual(low_density["estimated_gross_benefit"], 10000)
        self.assertEqual(high_density["estimated_gross_benefit"], 10000)
        self.assertLess(low_density["local_fit_score"], high_density["local_fit_score"])

    def test_previous_month_requirement_makes_card_ineligible(self):
        card = {
            "id": 1,
            "name": "Requirement Card",
            "issuer": "Issuer",
            "focus": ["cafe"],
            "discount_rate": 0.1,
            "annual_fee": 12000,
            "monthly_discount_limit": 30000,
            "previous_month_requirement": 300000,
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"cafe": 100000},
            infrastructure={"cafe": 10},
            previous_month_spending=100000,
        )

        self.assertEqual(result["estimated_gross_benefit"], 0)
        self.assertEqual(result["estimated_net_value"], -1000)
        self.assertFalse(result["is_eligible"])
        self.assertEqual(result["eligibility_status"], "전월 실적 미충족")

    def test_annual_fee_is_converted_to_monthly_cost(self):
        card = {
            "id": 1,
            "name": "Annual Fee Card",
            "issuer": "Issuer",
            "focus": ["cafe"],
            "discount_rate": 0.1,
            "annual_fee": 12000,
            "monthly_discount_limit": 30000,
            "previous_month_requirement": 0,
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"cafe": 100000},
            infrastructure={"cafe": 5},
        )

        self.assertEqual(result["monthly_annual_fee"], 1000)
        self.assertEqual(result["estimated_net_value"], 9000)

    def test_missing_spending_uses_cold_start_profile(self):
        card = {
            "id": 1,
            "name": "Cold Start Card",
            "issuer": "Issuer",
            "focus": ["cafe"],
            "discount_rate": 0.1,
            "annual_fee": 0,
            "monthly_discount_limit": 30000,
            "previous_month_requirement": 0,
        }

        result = calculate_card_recommendation(
            card=card,
            spending=None,
            fallback_spending={"cafe": 50000},
        )

        self.assertEqual(result["estimated_gross_benefit"], 5000)
        self.assertEqual(result["spending_profile"]["source"], "cohort_default")
        self.assertTrue(result["spending_profile"]["is_cold_start"])

    def test_transaction_rules_apply_minimum_per_transaction_and_usage_limits(self):
        card = {
            "id": 1,
            "name": "Transaction Card",
            "issuer": "Issuer",
            "focus": ["cafe"],
            "annual_fee": 0,
            "monthly_discount_limit": 30000,
            "previous_month_requirement": 0,
            "benefits": [
                {
                    "category": "cafe",
                    "discount_type": "rate",
                    "discount_rate": 0.5,
                    "minimum_transaction_amount": 5000,
                    "per_transaction_limit": 3000,
                    "monthly_usage_limit": 2,
                    "category_monthly_limit": 10000,
                }
            ],
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"cafe": 28000},
            transactions=[
                {"category": "cafe", "amount": 4000},
                {"category": "cafe", "amount": 6000},
                {"category": "cafe", "amount": 18000},
            ],
        )

        detail = result["calculation_breakdown"][0]
        self.assertEqual(detail["calculation_mode"], "transaction")
        self.assertEqual(detail["transaction_count"], 2)
        self.assertEqual(detail["final_benefit"], 6000)

    def test_merchant_scope_only_counts_matching_transactions(self):
        card = {
            "id": 1,
            "name": "Merchant Card",
            "issuer": "Issuer",
            "focus": ["cafe"],
            "annual_fee": 0,
            "previous_month_requirement": 0,
            "benefits": [
                {
                    "category": "cafe",
                    "discount_type": "rate",
                    "discount_rate": 0.05,
                    "merchant_scope": ["스타벅스", "이디야"],
                }
            ],
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"cafe": 50000},
            transactions=[
                {
                    "category": "cafe",
                    "merchant_name": "스타벅스 강남역점",
                    "amount": 10000,
                },
                {
                    "category": "cafe",
                    "merchant_name": "동네커피",
                    "amount": 20000,
                },
                {
                    "category": "cafe",
                    "merchant_name": "이디야_역삼점",
                    "amount": 20000,
                },
            ],
        )

        detail = result["calculation_breakdown"][0]
        self.assertEqual(result["estimated_gross_benefit"], 1500)
        self.assertEqual(detail["matched_transaction_count"], 2)
        self.assertEqual(detail["excluded_transaction_count"], 1)
        self.assertIsNone(detail["exclusion_reason"])

    def test_merchant_scope_without_transaction_details_returns_zero(self):
        card = {
            "id": 1,
            "name": "Merchant Card",
            "issuer": "Issuer",
            "focus": ["convenience"],
            "annual_fee": 0,
            "previous_month_requirement": 0,
            "benefits": [
                {
                    "category": "convenience",
                    "discount_type": "rate",
                    "discount_rate": 0.05,
                    "merchant_scope": ["GS25", "CU"],
                }
            ],
        }

        result = calculate_card_recommendation(
            card=card,
            spending={"convenience": 100000},
        )

        detail = result["calculation_breakdown"][0]
        self.assertEqual(result["estimated_gross_benefit"], 0)
        self.assertEqual(
            detail["calculation_mode"],
            "merchant_scope_unavailable",
        )
        self.assertEqual(
            detail["exclusion_reason"],
            "가맹점명이 포함된 거래 데이터가 필요함",
        )

    def test_owned_card_has_badge_but_no_ranking_bonus(self):
        cards = [
            {
                "id": 1,
                "name": "Owned",
                "issuer": "Issuer",
                "focus": ["cafe"],
                "discount_rate": 0.05,
                "annual_fee": 0,
                "monthly_discount_limit": 30000,
                "previous_month_requirement": 0,
            },
            {
                "id": 2,
                "name": "Better",
                "issuer": "Issuer",
                "focus": ["cafe"],
                "discount_rate": 0.1,
                "annual_fee": 0,
                "monthly_discount_limit": 30000,
                "previous_month_requirement": 0,
            },
        ]

        results = rank_card_recommendations(
            cards=cards,
            spending={"cafe": 100000},
            infrastructure={"cafe": 8},
            owned_card_ids=[1],
        )

        self.assertEqual(results[0]["id"], 2)
        self.assertTrue(results[1]["is_owned"])
        self.assertEqual(results[1]["badge"], "보유중인 카드")

    def test_ranking_changes_with_local_fit(self):
        cards = [
            {
                "id": 1,
                "name": "Higher Net",
                "issuer": "Issuer",
                "focus": ["mart"],
                "discount_rate": 0.11,
                "annual_fee": 0,
                "monthly_discount_limit": 30000,
                "previous_month_requirement": 0,
            },
            {
                "id": 2,
                "name": "Higher Local Fit",
                "issuer": "Issuer",
                "focus": ["cafe"],
                "discount_rate": 0.1,
                "annual_fee": 0,
                "monthly_discount_limit": 30000,
                "previous_month_requirement": 0,
            },
        ]

        mart_first = rank_card_recommendations(
            cards=cards,
            spending={"cafe": 100000, "mart": 100000},
            infrastructure={"cafe": 1, "mart": 20},
        )
        cafe_first = rank_card_recommendations(
            cards=cards,
            spending={"cafe": 100000, "mart": 100000},
            infrastructure={"cafe": 20, "mart": 1},
        )

        self.assertEqual(mart_first[0]["id"], 1)
        self.assertEqual(cafe_first[0]["id"], 2)
        self.assertGreater(mart_first[0]["local_fit_score"], mart_first[1]["local_fit_score"])
        self.assertGreater(cafe_first[0]["local_fit_score"], cafe_first[1]["local_fit_score"])
