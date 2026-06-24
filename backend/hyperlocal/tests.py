from decimal import Decimal
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings, SimpleTestCase
from rest_framework.test import APITestCase

from finance.merchant_normalization import normalize_merchant_brand
from finance.models import (
    BenefitRule,
    CardProduct,
    CardType,
    DiscountType,
    ParseStatus,
)
from hyperlocal.services import (
    build_vlm_payload,
    build_area_id_from_coordinates,
    collect_kakao_category_places,
    parse_consumption_image,
)
from users.models import UserCardEvent, UserConsumptionProfile, UserOwnedCard


class FakeHttpResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class VlmConsumptionParserTests(SimpleTestCase):
    def make_file(self):
        return SimpleUploadedFile(
            "receipt.png",
            b"fake-image-bytes",
            content_type="image/png",
        )

    @override_settings(
        VLM_MODEL="test-model",
        VLM_API_TYPE="chat_completions",
        VLM_GMS_COMPAT=True,
    )
    def test_gms_compat_omits_response_format(self):
        payload = build_vlm_payload(
            data_url="data:image/png;base64,abc",
            filename="receipt.png",
            mime_type="image/png",
        )

        self.assertEqual(payload["model"], "test-model")
        self.assertIn("messages", payload)
        self.assertNotIn("response_format", payload)

    @override_settings(
        VLM_MODEL="test-model",
        VLM_API_TYPE="chat_completions",
        VLM_GMS_COMPAT=True,
        VLM_GMS_STRICT=True,
    )
    def test_gms_strict_keeps_only_model_and_messages(self):
        payload = build_vlm_payload(
            data_url="data:image/png;base64,abc",
            filename="receipt.png",
            mime_type="image/png",
        )

        self.assertEqual(sorted(payload.keys()), ["messages", "model"])

    @override_settings(
        VLM_API_TYPE="gemini_generate_content",
        VLM_MODEL="gemini-3.5-flash",
    )
    def test_gemini_payload_uses_inline_data(self):
        payload = build_vlm_payload(
            data_url="data:image/png;base64,abc",
            filename="receipt.png",
            mime_type="image/png",
        )

        parts = payload["contents"][0]["parts"]
        self.assertEqual(parts[1]["inlineData"]["mimeType"], "image/png")
        self.assertEqual(parts[1]["inlineData"]["data"], "abc")
        self.assertEqual(sorted(payload.keys()), ["contents"])

    @override_settings(VLM_API_URL="", VLM_API_KEY="", VLM_MODEL="")
    def test_parser_falls_back_when_vlm_is_not_configured(self):
        parsed = parse_consumption_image(self.make_file())

        self.assertEqual(parsed["source"], "mock_vision_parser")
        self.assertEqual(parsed["fallback_reason"], "vlm_not_configured")
        self.assertIn("cafe", parsed["spending"])

    @override_settings(
        VLM_API_URL="https://example.com/vlm",
        VLM_API_KEY="test-key",
        VLM_MODEL="test-model",
        VLM_API_TYPE="chat_completions",
    )
    @patch("hyperlocal.services.urlopen")
    def test_parser_normalizes_vlm_json_response(self, urlopen_mock):
        urlopen_mock.return_value = FakeHttpResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "spending": {
                                        "카페": "102,000",
                                        "편의점": 58000,
                                        "음식점": 183000,
                                        "마트": 89000,
                                        "쇼핑": 44000,
                                    },
                                    "confidence": 0.87,
                                    "summary": "소비 리포트 분석 완료",
                                }
                            )
                        }
                    }
                ]
            }
        )

        parsed = parse_consumption_image(self.make_file())

        self.assertEqual(parsed["source"], "vlm")
        self.assertEqual(parsed["confidence"], 0.87)
        self.assertEqual(parsed["spending"]["cafe"], 102000)
        self.assertEqual(parsed["spending"]["convenience"], 58000)
        self.assertEqual(parsed["spending"]["dining"], 183000)
        self.assertEqual(parsed["spending"]["mart"], 89000)
        self.assertEqual(parsed["spending"]["shopping"], 44000)

    @override_settings(
        VLM_API_URL="https://example.com/gemini",
        VLM_API_KEY="test-key",
        VLM_MODEL="gemini-3.5-flash",
        VLM_API_TYPE="gemini_generate_content",
    )
    @patch("hyperlocal.services.urlopen")
    def test_parser_normalizes_gemini_json_response(self, urlopen_mock):
        urlopen_mock.return_value = FakeHttpResponse(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "spending": {"cafe": 12000, "delivery": 34000},
                                            "confidence": 0.75,
                                            "summary": "Gemini parsed",
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            }
        )

        parsed = parse_consumption_image(self.make_file())

        self.assertEqual(parsed["source"], "vlm")
        self.assertEqual(parsed["spending"]["cafe"], 12000)
        self.assertEqual(parsed["spending"]["delivery"], 34000)
        self.assertEqual(parsed["confidence"], 0.75)

    @override_settings(
        VLM_API_URL="https://example.com/vlm",
        VLM_API_KEY="test-key",
        VLM_MODEL="test-model",
    )
    @patch("hyperlocal.services.urlopen")
    def test_parser_falls_back_when_vlm_response_is_invalid(self, urlopen_mock):
        urlopen_mock.return_value = FakeHttpResponse({"choices": [{"message": {"content": "not json"}}]})

        parsed = parse_consumption_image(self.make_file())

        self.assertEqual(parsed["source"], "mock_vision_parser")
        self.assertIn("VLM response did not include JSON", parsed["fallback_reason"])


class MerchantInfrastructureTests(SimpleTestCase):
    def test_coordinates_are_converted_to_stable_area_id(self):
        self.assertEqual(
            build_area_id_from_coordinates(37.49791, 127.02762),
            "geo_37_497_127_027",
        )

    def test_brand_aliases_are_normalized(self):
        self.assertEqual(
            normalize_merchant_brand("CU 媛뺣궓?濡쒖젏"),
            "CU",
        )
        self.assertIsNone(normalize_merchant_brand("Independent Cafe Gangnam"))

    @patch("hyperlocal.services.kakao_category_search")
    def test_kakao_places_are_collected_across_pages(self, search):
        search.side_effect = [
            {
                "meta": {"total_count": 4, "is_end": False},
                "documents": [
                    {"id": "1", "place_name": "Starbucks Gangnam"},
                    {"id": "2", "place_name": "Mega MGC Coffee Yeoksam"},
                ],
            },
            {
                "meta": {"total_count": 4, "is_end": True},
                "documents": [
                    {"id": "3", "place_name": "Starbucks Seolleung"},
                    {"id": "4", "place_name": "媛쒖씤移댄럹"},
                ],
            },
        ]

        result = collect_kakao_category_places(
            "CE7",
            37.5,
            127.0,
            500,
        )

        self.assertEqual(search.call_count, 2)
        self.assertEqual(result["total_count"], 4)
        self.assertEqual(result["sample_count"], 4)
        self.assertFalse(result["is_sampled"])
        self.assertEqual(sum(result["merchant_counts"].values()), 3)


class SimulateApiTests(APITestCase):
    url = "/api/v1/hyperlocal/simulate/"

    def create_card(self, parse_status=ParseStatus.ACTIVE):
        card = CardProduct.objects.create(
            external_id=f"card-{parse_status}",
            issuer="Test Issuer",
            provider="Test Issuer",
            source_channel="test",
            card_type=CardType.CREDIT,
            name=f"{parse_status} 移대뱶",
            source_url=f"https://example.com/{parse_status}",
            annual_fee=12000 if parse_status == ParseStatus.ACTIVE else None,
            previous_month_requirement=0,
            monthly_discount_limit=30000,
            parse_status=parse_status,
            raw_text="移대뱶 ?먮Ц",
        )
        BenefitRule.objects.create(
            card=card,
            category="cafe",
            discount_type=DiscountType.RATE,
            discount_rate=Decimal("0.1"),
            raw_text="移댄럹 10% ?좎씤",
            parse_status=(
                ParseStatus.ACTIVE
                if parse_status == ParseStatus.ACTIVE
                else ParseStatus.REVIEW_REQUIRED
            ),
        )
        return card

    def test_no_active_cards_returns_explicit_empty_state(self):
        self.create_card(ParseStatus.REVIEW_REQUIRED)

        response = self.client.post(
            self.url,
            {"spending": {"cafe": 100000}},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["recommendation_source"], "sqlite")
        self.assertEqual(response.data["candidate_count"], 0)
        self.assertEqual(response.data["excluded_review_count"], 1)
        self.assertEqual(response.data["fallback_reason"], "no_active_cards")
        self.assertEqual(response.data["card_ranking_list"], [])
        self.assertIsNone(response.data["best_card"])

    @patch("hyperlocal.services.load_recommendation_candidates")
    def test_area_id_is_passed_to_candidate_loader(self, load_candidates):
        load_candidates.return_value = {
            "cards": [],
            "metadata": {
                "recommendation_source": "neo4j",
                "candidate_count": 0,
                "excluded_review_count": 0,
                "excluded_invalid_count": 0,
                "excluded_inactive_count": 0,
                "excluded_unready_count": 0,
                "fallback_reason": "no_graph_candidates",
            },
        }

        response = self.client.post(
            self.url,
            {
                "area_id": "gangnam_station",
                "spending": {"cafe": 100000},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        load_candidates.assert_called_once_with(area_id="gangnam_station")
        self.assertEqual(response.data["area_id"], "gangnam_station")
        self.assertEqual(response.data["recommendation_source"], "neo4j")

    @patch("hyperlocal.views.sync_area_graph_for_coordinates")
    @patch("hyperlocal.services.load_recommendation_candidates")
    def test_sync_area_uses_click_coordinates_before_recommendation(
        self,
        load_candidates,
        sync_area,
    ):
        load_candidates.return_value = {
            "cards": [],
            "metadata": {
                "recommendation_source": "sqlite",
                "candidate_count": 0,
                "excluded_review_count": 0,
                "excluded_invalid_count": 0,
                "excluded_inactive_count": 0,
                "excluded_unready_count": 0,
                "graph_candidate_count": 0,
                "graph_status": "no_candidates",
                "graph_fallback_reason": "no_graph_candidates",
                "fallback_reason": "no_active_cards",
            },
        }
        sync_area.return_value = {
            "area_sync_status": "synced",
            "area_sync_store_count": 12,
            "area_sync_error": None,
        }

        response = self.client.post(
            self.url,
            {
                "user_id": 1,
                "lat": 37.49791,
                "lng": 127.02762,
                "radius": 500,
                "sync_area": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["area_id"], "geo_37_497_127_027")
        self.assertEqual(response.data["area_sync_status"], "synced")
        self.assertEqual(response.data["area_sync_store_count"], 12)
        sync_area.assert_called_once_with(
            area_id="geo_37_497_127_027",
            area_name="selected_geo_37_497_127_027",
            lat=37.49791,
            lng=127.02762,
            radius=500,
        )
        load_candidates.assert_called_once_with(
            area_id="geo_37_497_127_027"
        )

    @patch("hyperlocal.views.sync_user_graph_profile")
    @patch("hyperlocal.services.load_recommendation_candidates")
    def test_user_graph_profile_is_synced_with_area_and_owned_cards(
        self,
        load_candidates,
        sync_user_graph,
    ):
        card = self.create_card(ParseStatus.ACTIVE)
        user = get_user_model().objects.create_user(
            username="graph-user",
            email="graph-user@example.com",
            password="secret",
        )
        UserOwnedCard.objects.create(user=user, card=card)
        load_candidates.return_value = {
            "cards": [],
            "metadata": {
                "recommendation_source": "neo4j",
                "candidate_count": 0,
                "excluded_review_count": 0,
                "excluded_invalid_count": 0,
                "excluded_inactive_count": 0,
                "excluded_unready_count": 0,
                "graph_candidate_count": 0,
                "graph_status": "no_candidates",
                "graph_fallback_reason": "no_graph_candidates",
                "fallback_reason": "no_active_cards",
            },
        }
        sync_user_graph.return_value = {
            "user_graph_status": "synced",
            "user_graph_owned_card_count": 1,
            "user_graph_error": None,
        }

        response = self.client.post(
            self.url,
            {
                "user_id": user.id,
                "area_id": "geo_37_497_127_027",
                "spending": {"cafe": 100000},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user_graph_status"], "synced")
        self.assertEqual(response.data["user_graph_owned_card_count"], 1)
        sync_user_graph.assert_called_once_with(
            user_id=user.id,
            area_id="geo_37_497_127_027",
            area_name="selected_geo_37_497_127_027",
            owned_card_ids=[card.pk],
        )

    @patch("hyperlocal.views.sync_user_graph_profile")
    @patch("hyperlocal.services.load_recommendation_candidates")
    def test_user_graph_failure_does_not_block_recommendation(
        self,
        load_candidates,
        sync_user_graph,
    ):
        card = self.create_card(ParseStatus.ACTIVE)
        user = get_user_model().objects.create_user(
            username="graph-failure-user",
            email="graph-failure-user@example.com",
            password="secret",
        )
        load_candidates.return_value = {
            "cards": [
                {
                    "id": card.pk,
                    "name": card.name,
                    "issuer": card.issuer,
                    "card_type": card.card_type,
                    "focus": ["cafe"],
                    "annual_fee": card.annual_fee,
                    "previous_month_requirement": 0,
                    "monthly_discount_limit": 30000,
                    "benefits": [
                        {
                            "category": "cafe",
                            "discount_type": "rate",
                            "discount_rate": 0.1,
                        }
                    ],
                    "benefit_tiers": [],
                    "service_limit_tiers": [],
                }
            ],
            "metadata": {
                "recommendation_source": "neo4j",
                "candidate_count": 1,
                "excluded_review_count": 0,
                "excluded_invalid_count": 0,
                "excluded_inactive_count": 0,
                "excluded_unready_count": 0,
                "graph_candidate_count": 1,
                "graph_status": "matched",
                "graph_fallback_reason": None,
                "fallback_reason": None,
            },
        }
        sync_user_graph.side_effect = RuntimeError("neo4j down")

        response = self.client.post(
            self.url,
            {
                "user_id": user.id,
                "area_id": "geo_37_497_127_027",
                "spending": {"cafe": 100000},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user_graph_status"], "failed")
        self.assertIn("neo4j down", response.data["user_graph_error"])
        self.assertEqual(response.data["best_card"]["id"], card.pk)

    def test_active_card_is_ranked_from_sqlite(self):
        card = self.create_card(ParseStatus.ACTIVE)

        response = self.client.post(
            self.url,
            {
                "spending": {"cafe": 100000},
                "previous_month_spending": 100000,
                "owned_card_ids": [card.pk],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["recommendation_source"], "sqlite")
        self.assertEqual(response.data["candidate_count"], 1)
        self.assertEqual(response.data["best_card"]["id"], card.pk)
        self.assertEqual(
            response.data["best_card"]["estimated_net_value"],
            9000,
        )
        self.assertTrue(response.data["best_card"]["is_owned"])

    def test_simulate_uses_saved_vlm_consumption_profile_when_user_id_is_sent(self):
        card = self.create_card(ParseStatus.ACTIVE)
        user = get_user_model().objects.create_user(
            username="vlm-sim-user",
            email="vlm-sim@example.com",
            password="secret",
        )
        UserConsumptionProfile.objects.create(
            user=user,
            source="image_parser",
            spending_json={
                "cafe": 102000,
                "convenience": 58000,
                "dining": 183000,
                "mart": 89000,
            },
            is_cold_start=False,
        )

        response = self.client.post(
            self.url,
            {
                "user_id": user.id,
                "previous_month_spending": 500000,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user_id"], user.id)
        self.assertEqual(response.data["spending"]["cafe"], 102000)
        self.assertEqual(response.data["spending_profile"]["source"], "image_parser")
        self.assertFalse(response.data["spending_profile"]["is_cold_start"])
        self.assertEqual(response.data["best_card"]["id"], card.pk)
        self.assertEqual(response.data["best_card"]["ranking_mode"], "overall")

    def test_selected_category_and_brand_infrastructure_are_returned(self):
        card = self.create_card(ParseStatus.ACTIVE)
        benefit = card.benefits.get()
        benefit.merchant_scope = ["?ㅽ?踰낆뒪"]
        benefit.save(update_fields=["merchant_scope", "updated_at"])

        response = self.client.post(
            self.url,
            {
                "spending": {"cafe": 100000},
                "selected_category": "cafe",
                "infrastructure": [
                    {
                        "key": "cafe",
                        "category": "移댄럹",
                        "count": 20,
                        "total_count": 20,
                        "sample_count": 10,
                        "is_sampled": True,
                        "merchant_counts": {"?ㅽ?踰낆뒪": 4},
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["selected_category"], "cafe")
        self.assertEqual(response.data["best_card"]["ranking_mode"], "category")
        category_score = response.data["best_card"]["category_scores"]["cafe"]
        self.assertEqual(category_score["merchant_accessibility"], 40.0)
        self.assertGreater(category_score["category_fit_score"], 0)
        self.assertEqual(
            response.data["best_card"]["ranking_score"],
            category_score["category_fit_score"],
        )

    def test_missing_previous_month_spending_uses_cold_start_estimate(self):
        card = self.create_card(ParseStatus.ACTIVE)
        card.previous_month_requirement = 300000
        card.save(update_fields=["previous_month_requirement", "updated_at"])

        response = self.client.post(
            self.url,
            {"selected_category": "cafe"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        profile = response.data["previous_month_spending_profile"]
        self.assertTrue(profile["is_estimated"])
        self.assertEqual(profile["source"], "cohort_default")
        self.assertGreaterEqual(profile["amount"], 300000)
        self.assertTrue(response.data["best_card"]["is_eligible"])
        self.assertEqual(response.data["selected_category"], "cafe")

    def test_explicit_zero_previous_month_spending_is_not_estimated(self):
        card = self.create_card(ParseStatus.ACTIVE)
        card.previous_month_requirement = 300000
        card.save(update_fields=["previous_month_requirement", "updated_at"])

        response = self.client.post(
            self.url,
            {"previous_month_spending": 0},
            format="json",
        )

        profile = response.data["previous_month_spending_profile"]
        self.assertFalse(profile["is_estimated"])
        self.assertEqual(profile["amount"], 0)
        self.assertFalse(response.data["best_card"]["is_eligible"])

    def test_api_applies_merchant_scope_from_sqlite(self):
        card = self.create_card(ParseStatus.ACTIVE)
        benefit = card.benefits.get()
        benefit.merchant_scope = ["?ㅽ?踰낆뒪"]
        benefit.save(update_fields=["merchant_scope", "updated_at"])

        response = self.client.post(
            self.url,
            {
                "spending": {"cafe": 30000},
                "transactions": [
                    {
                        "category": "cafe",
                        "merchant_name": "?ㅽ?踰낆뒪 媛뺣궓??젏",
                        "amount": 10000,
                    },
                    {
                        "category": "cafe",
                        "merchant_name": "?숇꽕而ㅽ뵾",
                        "amount": 20000,
                    },
                ],
            },
            format="json",
        )

        detail = response.data["best_card"]["calculation_breakdown"][0]
        self.assertEqual(response.data["best_card"]["estimated_gross_benefit"], 1000)
        self.assertEqual(detail["matched_transaction_count"], 1)
        self.assertEqual(detail["excluded_transaction_count"], 1)

    def test_mock_fallback_requires_explicit_flag(self):
        response = self.client.post(
            self.url,
            {
                "spending": {"cafe": 100000},
                "previous_month_spending": 400000,
                "allow_mock_fallback": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["recommendation_source"],
            "mock_fallback",
        )
        self.assertEqual(response.data["candidate_count"], 3)
        self.assertEqual(len(response.data["card_ranking_list"]), 3)


class CardEventApiTests(APITestCase):
    url = "/api/v1/hyperlocal/card-events/"

    def create_user_and_card(self):
        user = get_user_model().objects.create_user(
            username="event-user",
            email="event-user@example.com",
            password="secret",
        )
        card = CardProduct.objects.create(
            external_id="event-card",
            issuer="Test Issuer",
            provider="Test Issuer",
            source_channel="test",
            card_type=CardType.CREDIT,
            name="Event Card",
            source_url="https://example.com/event-card",
            annual_fee=12000,
            previous_month_requirement=0,
            parse_status=ParseStatus.ACTIVE,
            raw_text="event card raw text",
        )
        return user, card

    @patch("finance.graph_repository.GraphRepository.create_user_card_event")
    def test_card_event_is_saved_and_synced_to_graph(self, create_event):
        user, card = self.create_user_and_card()

        response = self.client.post(
            self.url,
            {
                "user_id": user.id,
                "card_id": card.pk,
                "area_id": "geo_37_497_127_027",
                "event_type": "clicked",
                "metadata": {"rank": 1, "source": "map_recommendation"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["event_status"], "synced")
        event = UserCardEvent.objects.get(pk=response.data["event_id"])
        self.assertEqual(event.graph_sync_status, "synced")
        self.assertEqual(event.event_type, "clicked")
        create_event.assert_called_once()

    @patch("finance.graph_repository.GraphRepository.create_user_card_event")
    def test_card_event_remains_saved_when_graph_sync_fails(self, create_event):
        user, card = self.create_user_and_card()
        create_event.side_effect = RuntimeError("neo4j unavailable")

        response = self.client.post(
            self.url,
            {
                "user_id": user.id,
                "card_id": card.pk,
                "event_type": "liked",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["event_status"], "saved_graph_failed")
        event = UserCardEvent.objects.get(pk=response.data["event_id"])
        self.assertEqual(event.graph_sync_status, "failed")
        self.assertIn("neo4j unavailable", event.graph_sync_error)

    def test_card_event_rejects_invalid_event_type(self):
        user, card = self.create_user_and_card()

        response = self.client.post(
            self.url,
            {
                "user_id": user.id,
                "card_id": card.pk,
                "event_type": "unknown",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(UserCardEvent.objects.count(), 0)

    def test_area_card_popularity_ranks_by_events_and_category_fit(self):
        user, first_card = self.create_user_and_card()
        second_card = CardProduct.objects.create(
            external_id="event-card-2",
            issuer="Test Issuer",
            provider="Test Issuer",
            source_channel="test",
            card_type=CardType.CREDIT,
            name="Second Event Card",
            source_url="https://example.com/event-card-2",
            annual_fee=12000,
            previous_month_requirement=0,
            parse_status=ParseStatus.ACTIVE,
            raw_text="event card raw text",
        )
        area_id = "geo_37_497_127_027"
        UserCardEvent.objects.create(
            user=user,
            card=first_card,
            area_id=area_id,
            event_type="viewed",
        )
        UserCardEvent.objects.create(
            user=user,
            card=first_card,
            area_id=area_id,
            event_type="clicked",
        )
        UserCardEvent.objects.create(
            user=user,
            card=first_card,
            area_id=area_id,
            event_type="liked",
        )
        UserCardEvent.objects.create(
            user=user,
            card=second_card,
            area_id=area_id,
            event_type="viewed",
        )

        response = self.client.post(
            "/api/v1/hyperlocal/area-card-popularity/",
            {
                "area_id": area_id,
                "cards": [
                    {
                        "card_id": first_card.pk,
                        "graph_matched_categories": ["cafe", "dining"],
                        "graph_category_shares": {"cafe": 0.35, "dining": 0.28},
                        "graph_rerank_score": 40,
                        "seul_score": 70,
                    },
                    {
                        "card_id": second_card.pk,
                        "graph_matched_categories": ["cafe"],
                        "graph_category_shares": {"cafe": 0.35},
                        "graph_rerank_score": 99,
                        "seul_score": 99,
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        first = response.data["ranking"][0]
        self.assertEqual(first["card_id"], first_card.pk)
        self.assertEqual(first["event_score"], 9)
        self.assertEqual(first["category_fit"], 0.63)
        self.assertEqual(first["local_popularity_score"], 14.67)

    def test_area_card_popularity_requires_area_and_cards(self):
        response = self.client.post(
            "/api/v1/hyperlocal/area-card-popularity/",
            {"area_id": "geo_37_497_127_027", "cards": []},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
