from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from finance.models import CardImage, CardProduct, CardType, CrawlStatus, ParseStatus

from .models import (
    UserConsumptionProfile,
    UserOwnedCard,
    UserProfile,
    UserUploadedReport,
)
from .views import ConsumptionProfileUpsertView
from .views import OwnedCardUpsertView
from .views import ProfileView
from .views import UploadedReportCreateView


class ProfileViewTests(TestCase):
    def test_profile_view_returns_database_backed_profile(self):
        user = get_user_model().objects.create_user(
            username="demo-user",
            email="demo@example.com",
            password="secret",
        )
        profile = UserProfile.objects.create(
            user=user,
            nickname="데모",
            preferred_area="서울 강남구",
            monthly_expected_spend=250000,
        )
        card = CardProduct.objects.create(
            external_id="demo-card",
            issuer="테스트카드",
            provider="테스트카드",
            source_channel="test",
            card_type=CardType.CREDIT,
            name="데모카드",
            source_url="https://example.com/card",
            annual_fee=10000,
            parse_status=ParseStatus.ACTIVE,
            raw_text="데모",
        )
        UserOwnedCard.objects.create(user=user, card=card)
        UserUploadedReport.objects.create(
            user=user,
            file_url="https://example.com/report.pdf",
            file_type="pdf",
            parse_status=ParseStatus.RAW,
        )
        UserConsumptionProfile.objects.create(
            user=user,
            source="image_parser",
            spending_json={"cafe": 102000, "dining": 183000},
            is_cold_start=False,
        )

        request = APIRequestFactory().get("/api/v1/users/profile/")
        response = ProfileView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "demo-user")
        self.assertEqual(response.data["nickname"], "데모")
        self.assertEqual(response.data["home_address"], "서울 강남구")
        self.assertEqual(response.data["monthly_expected_spend"], 250000)
        self.assertEqual(response.data["favorite_cards"][0]["name"], "데모카드")
        self.assertEqual(
            response.data["uploaded_report"]["file_url"],
            "https://example.com/report.pdf",
        )
        self.assertEqual(
            response.data["consumption_profile"]["source"],
            "image_parser",
        )
        self.assertEqual(
            response.data["consumption_profile"]["spending_json"]["dining"],
            183000,
        )

    def test_frontend_profile_includes_owned_card_details_with_image(self):
        user = get_user_model().objects.create_user(
            username="owned-detail-user",
            email="owned-detail@example.com",
            password="secret",
        )
        card = CardProduct.objects.create(
            external_id="owned-detail-card",
            issuer="Test Issuer",
            provider="Test Issuer",
            source_channel="test",
            card_type=CardType.CREDIT,
            name="Owned Detail Card",
            source_url="https://example.com/owned-detail-card",
            annual_fee=10000,
            parse_status=ParseStatus.ACTIVE,
            raw_text="test",
        )
        CardImage.objects.create(
            card=card,
            source_url="https://example.com/card.png",
            download_status=CrawlStatus.PENDING,
            is_primary=True,
        )
        UserOwnedCard.objects.create(user=user, card=card)

        profile = ProfileView.as_view()(
            APIRequestFactory().get("/api/v1/users/profile/")
        )

        # The demo fallback user resolver picks the first user when no user_id is supplied.
        self.assertEqual(profile.data["ownedCardDetails"][0]["name"], "Owned Detail Card")
        self.assertEqual(
            profile.data["ownedCardDetails"][0]["image_url"],
            "https://example.com/card.png",
        )

    def test_profile_post_creates_or_updates_profile(self):
        request = APIRequestFactory().post(
            "/api/v1/users/profile/",
            {
                "email": "new@example.com",
                "password": "secret",
                "nickname": "새사용자",
                "preferred_area": "서울 마포구",
                "monthly_expected_spend": 300000,
            },
            format="json",
        )
        response = ProfileView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["nickname"], "새사용자")
        self.assertEqual(
            get_user_model().objects.get(username="new").seulpick_profile.nickname,
            "새사용자",
        )

    def test_profile_view_returns_consumption_profile_without_user_profile(self):
        user = get_user_model().objects.create_user(
            username="vlm-only",
            email="vlm-only@example.com",
            password="secret",
        )
        UserConsumptionProfile.objects.create(
            user=user,
            source="image_parser",
            spending_json={"cafe": 102000, "shopping": 44000},
            is_cold_start=False,
        )

        request = APIRequestFactory().get("/api/v1/users/profile/")
        response = ProfileView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "vlm-only")
        self.assertEqual(
            response.data["consumption_profile"]["spending_json"]["shopping"],
            44000,
        )

    def test_owned_cards_post_creates_mappings(self):
        user = get_user_model().objects.create_user(
            username="card-user",
            email="card@example.com",
            password="secret",
        )
        card = CardProduct.objects.create(
            external_id="card-1",
            issuer="테스트",
            provider="테스트",
            source_channel="test",
            card_type=CardType.CREDIT,
            name="카드1",
            source_url="https://example.com/card-1",
            annual_fee=10000,
            parse_status=ParseStatus.ACTIVE,
            raw_text="테스트",
        )

        request = APIRequestFactory().post(
            "/api/v1/users/owned-cards/",
            {"user_id": user.id, "card_ids": [card.id]},
            format="json",
        )
        response = OwnedCardUpsertView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["created_count"], 1)
        self.assertEqual(user.owned_cards.count(), 1)

    def test_owned_cards_post_accepts_manual_card_names(self):
        user = get_user_model().objects.create_user(
            username="manual-card-user",
            email="manual-card@example.com",
            password="secret",
        )

        request = APIRequestFactory().post(
            "/api/v1/users/owned-cards/",
            {"user_id": user.id, "manual_card_names": ["내 커스텀 카드"]},
            format="json",
        )
        response = OwnedCardUpsertView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["created_count"], 1)
        owned = user.owned_cards.select_related("card").get()
        self.assertEqual(owned.card.name, "내 커스텀 카드")
        self.assertEqual(owned.card.source_channel, "manual_user")
        self.assertIn("내 커스텀 카드", response.data["profile"]["ownedCards"])

    def test_owned_cards_post_removes_mappings(self):
        user = get_user_model().objects.create_user(
            username="remove-card-user",
            email="remove-card@example.com",
            password="secret",
        )
        card = CardProduct.objects.create(
            external_id="remove-card-1",
            issuer="Test",
            provider="Test",
            source_channel="test",
            card_type=CardType.CREDIT,
            name="Remove Card",
            source_url="https://example.com/remove-card",
            annual_fee=10000,
            parse_status=ParseStatus.ACTIVE,
            raw_text="test",
        )
        UserOwnedCard.objects.create(user=user, card=card)

        request = APIRequestFactory().post(
            "/api/v1/users/owned-cards/",
            {"user_id": user.id, "remove_card_ids": [card.id]},
            format="json",
        )
        response = OwnedCardUpsertView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["removed_count"], 1)
        self.assertEqual(user.owned_cards.count(), 0)
        self.assertNotIn("Remove Card", response.data["profile"]["ownedCards"])

    def test_consumption_profile_post_saves_json(self):
        user = get_user_model().objects.create_user(
            username="spend-user",
            email="spend@example.com",
            password="secret",
        )
        request = APIRequestFactory().post(
            "/api/v1/users/consumption-profile/",
            {
                "user_id": user.id,
                "source": "image_parser",
                "spending_json": {"cafe": 100000},
                "is_cold_start": False,
            },
            format="json",
        )
        response = ConsumptionProfileUpsertView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["source"], "image_parser")
        self.assertEqual(
            user.consumption_profile.spending_json,
            {"cafe": 100000},
        )

    def test_uploaded_report_with_vlm_spending_updates_consumption_profile(self):
        user = get_user_model().objects.create_user(
            username="vlm-user",
            email="vlm@example.com",
            password="secret",
        )

        request = APIRequestFactory().post(
            "/api/v1/users/reports/",
            {
                "user_id": user.id,
                "file_url": "local-vlm-upload://user-1/report.png",
                "file_type": "image/png",
                "parse_status": ParseStatus.NORMALIZED,
                "parsed_payload": {
                    "spending": {
                        "cafe": 102000,
                        "convenience": 58000,
                        "dining": 183000,
                        "mart": 89000,
                    }
                },
            },
            format="json",
        )
        response = UploadedReportCreateView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["consumption_profile_updated"])
        profile = UserConsumptionProfile.objects.get(user=user)
        self.assertEqual(profile.source, "image_parser")
        self.assertFalse(profile.is_cold_start)
        self.assertEqual(profile.spending_json["cafe"], 102000)
