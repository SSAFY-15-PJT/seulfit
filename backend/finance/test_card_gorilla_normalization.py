from django.test import SimpleTestCase

from finance.card_gorilla_normalization import (
    extract_merchant_scope,
    parse_annual_fee,
    parse_benefit,
    parse_card_gorilla_payload,
    parse_category_monthly_limit,
    parse_minimum_transaction_amount,
    parse_channel_condition,
)


class CardGorillaNormalizationTests(SimpleTestCase):
    def test_fee_parser_uses_lowest_available_fee(self):
        self.assertEqual(
            parse_annual_fee("국내전용 [20,000]원 / 해외겸용 [25,000]원"),
            20000,
        )
        self.assertEqual(parse_annual_fee("국내전용 [없음]"), 0)

    def test_benefit_parser_splits_multi_category_discount(self):
        benefits = parse_benefit(
            {
                "title": "생활",
                "comment": "음식점, 커피전문점, 편의점 10% 할인",
                "info": "<p>월 5회, 건당 최대 1천원 할인</p>",
            }
        )

        self.assertEqual(
            {benefit["category"] for benefit in benefits},
            {"dining", "cafe", "convenience"},
        )
        self.assertTrue(
            all(
                benefit["discount_rate"] == "0.1"
                and benefit["per_transaction_limit"] is None
                and benefit["monthly_usage_limit"] is None
                for benefit in benefits
            )
        )

    def test_universal_category_benefit_maps_to_supported_focuses(self):
        benefits = parse_benefit(
            {
                "title": "국내 전 가맹점",
                "comment": "국내 전 가맹점 0.3% 캐시백",
                "info": "<p>전월실적 및 월 캐시백 한도 제한없음</p>",
            }
        )

        self.assertEqual(
            {benefit["category"] for benefit in benefits},
            {"shopping"},
        )
        self.assertTrue(all(benefit["discount_rate"] == "0.003" for benefit in benefits))

    def test_delivery_is_not_mixed_with_dining(self):
        benefits = parse_benefit(
            {
                "title": "배달앱",
                "comment": "배달의민족, 쿠팡이츠 5% 캐시백",
                "info": "",
            }
        )

        self.assertEqual(
            {benefit["category"] for benefit in benefits},
            {"delivery"},
        )

    def test_payload_is_always_marked_for_official_review(self):
        parsed = parse_card_gorilla_payload(
            {
                "external_id": "100",
                "card_type": "debit",
                "detail_page_url": "https://www.card-gorilla.com/card/detail/100",
                "detail": {
                    "name": "테스트 체크카드",
                    "corp": {"name": "테스트카드"},
                    "annual_fee_basic": "국내전용 [없음]",
                    "pre_month_money": 200000,
                    "card_img": {"url": "https://example.com/card.png"},
                    "key_benefit": [
                        {
                            "title": "카페",
                            "comment": "커피 5% 할인",
                            "info": "",
                        }
                    ],
                },
            }
        )

        self.assertEqual(parsed["card_type"], "debit")
        self.assertEqual(parsed["annual_fee"], 0)
        self.assertEqual(parsed["benefits"][0]["category"], "cafe")
        self.assertTrue(parsed["review_reasons"])

    def test_minimum_transaction_amount_patterns(self):
        self.assertEqual(
            parse_minimum_transaction_amount(
                "건당 1만원 이상 이용 시 제공"
            ),
            10000,
        )
        self.assertEqual(
            parse_minimum_transaction_amount(
                "매출건당 2만원 이상 시 1천원 캐시백"
            ),
            20000,
        )
        self.assertEqual(
            parse_minimum_transaction_amount(
                "전월 이용실적 20만원 이상 시 제공"
            ),
            0,
        )
        self.assertEqual(
            parse_minimum_transaction_amount(
                "건당 10만원 미만 결제 30%, 건당 10만원 이상 결제 20%"
            ),
            0,
        )

    def test_single_monthly_limit_is_parsed(self):
        self.assertEqual(
            parse_category_monthly_limit(
                "월 할인한도 : 3천원 (월 3만원 이용금액까지 할인)"
            ),
            3000,
        )
        self.assertEqual(
            parse_category_monthly_limit(
                "월 할인횟수 1회 (월 할인한도 1천원 이내 제공)"
            ),
            1000,
        )

    def test_multiple_monthly_limits_are_not_guessed(self):
        self.assertIsNone(
            parse_category_monthly_limit(
                "커피 월 2천원, 편의점 월 1천원, 각각 2회 한"
            )
        )

    def test_benefit_maps_minimum_monthly_and_daily_limits(self):
        benefit = parse_benefit(
            {
                "title": "편의점",
                "comment": "편의점 10% 할인",
                "info": (
                    "<p>건당 1만원 이상 이용 시 제공</p>"
                    "<p>일 1회, 월 5회</p>"
                    "<p>월 할인한도 5천원</p>"
                ),
            }
        )[0]

        self.assertEqual(benefit["minimum_transaction_amount"], 10000)
        self.assertEqual(benefit["daily_usage_limit"], 1)
        self.assertEqual(benefit["monthly_usage_limit"], 5)
        self.assertEqual(benefit["category_monthly_limit"], 5000)

    def test_multi_category_entry_does_not_copy_category_specific_limits(self):
        benefits = parse_benefit(
            {
                "title": "혜택 프로모션",
                "comment": "배달, 편의점, 커피 캐시백",
                "info": (
                    "<p>배달 2만원 이상 결제 시 1천원 캐시백</p>"
                    "<p>편의점 5천원 이상 결제 시 100원 캐시백</p>"
                    "<p>커피 1만원 이상 결제 시 500원 캐시백</p>"
                ),
            }
        )

        self.assertTrue(benefits)
        self.assertEqual(
            {benefit["category"] for benefit in benefits},
            {"convenience", "cafe"},
        )
        self.assertTrue(
            all(
                benefit["minimum_transaction_amount"] == 0
                and benefit["category_monthly_limit"] is None
                and benefit["monthly_usage_limit"] is None
                and benefit["daily_usage_limit"] is None
                for benefit in benefits
            )
        )

    def test_extracts_category_specific_merchant_scopes(self):
        self.assertEqual(
            extract_merchant_scope(
                "delivery",
                "배달의민족, 쿠팡이츠, 요기요 5% 할인",
            ),
            ["배달의민족", "쿠팡이츠", "요기요"],
        )
        self.assertEqual(
            extract_merchant_scope(
                "convenience",
                "GS25, CU 5% 할인",
            ),
            ["CU", "GS25"],
        )

    def test_generic_category_scope_does_not_create_brand_filter(self):
        self.assertEqual(
            extract_merchant_scope(
                "cafe",
                "커피 업종 전체 5% 할인",
            ),
            [],
        )

    def test_benefit_stores_merchant_scope(self):
        benefit = parse_benefit(
            {
                "title": "배달앱",
                "comment": "배달의민족, 요기요 5% 할인",
                "info": "",
            }
        )[0]

        self.assertEqual(
            benefit["merchant_scope"],
            ["배달의민족", "요기요"],
        )

    def test_explicit_online_and_offline_channels(self):
        self.assertEqual(
            parse_channel_condition(
                "공식 홈페이지/앱을 통한 결제건에 한함"
            ),
            ("online", []),
        )
        self.assertEqual(
            parse_channel_condition(
                "오프라인 매장 현장 결제에 한함"
            ),
            ("offline", []),
        )

    def test_mixed_channel_is_not_guessed(self):
        channel, unsupported = parse_channel_condition(
            "온라인 결제건과 오프라인 결제건에 한함"
        )

        self.assertEqual(channel, "all")
        self.assertIn("mixed_channel_mapping", unsupported)

    def test_payment_method_is_separate_from_channel(self):
        channel, unsupported = parse_channel_condition(
            "오프라인 매장에서 APP 내 바코드 결제 시"
        )

        self.assertEqual(channel, "offline")
        self.assertIn("payment_method_condition", unsupported)

    def test_multi_category_entry_does_not_copy_channel(self):
        benefits = parse_benefit(
            {
                "title": "생활",
                "comment": "커피, 편의점 5% 할인",
                "info": (
                    "<p>커피는 온라인 결제건, "
                    "편의점은 오프라인 결제건에 한함</p>"
                ),
            }
        )

        self.assertTrue(benefits)
        self.assertTrue(
            all(
                benefit["channel"] == "all"
                and "mixed_channel_mapping"
                in benefit["unsupported_conditions"]
                for benefit in benefits
            )
        )

    def test_multi_category_shared_offline_condition_is_applied(self):
        benefits = parse_benefit(
            {
                "title": "생활",
                "comment": "커피전문점, 편의점 5% 할인",
                "info": (
                    "<p>커피전문점과 편의점 모두 "
                    "오프라인 매장 현장 결제에 한함</p>"
                ),
            }
        )

        self.assertTrue(benefits)
        self.assertTrue(
            all(benefit["channel"] == "offline" for benefit in benefits)
        )

    def test_long_multi_service_text_does_not_assign_channel(self):
        channel, unsupported = parse_channel_condition(
            ("프리미엄 서비스 안내 " * 300)
            + "일부 온라인 결제건에 한함"
        )

        self.assertEqual(channel, "all")
        self.assertIn("mixed_channel_mapping", unsupported)

    def test_channel_is_not_copied_from_unrelated_service_detail(self):
        benefits = parse_benefit(
            {
                "title": "프리미엄 서비스",
                "comment": "다양한 여행과 다이닝 혜택",
                "info": (
                    "<p>렌터카 홈페이지 온라인 결제 5% 할인</p>"
                    "<p>외식 브랜드 현장 할인</p>"
                ),
            }
        )

        self.assertTrue(benefits)
        self.assertTrue(all(benefit["channel"] == "all" for benefit in benefits))

    def test_choice_bundle_does_not_assign_channel_to_dining(self):
        benefit = parse_benefit(
            {
                "title": "선택형",
                "comment": "음식점, 온라인 쇼핑몰 중 택 1",
                "info": "<p>음식점 5%, 온라인 쇼핑몰 10% 할인</p>",
            }
        )[0]

        self.assertEqual(benefit["channel"], "all")
        self.assertIn(
            "mixed_channel_mapping",
            benefit["unsupported_conditions"],
        )
