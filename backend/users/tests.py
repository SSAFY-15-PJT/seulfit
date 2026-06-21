from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from finance.models import CardProduct, CardType, ParseStatus

from .models import UserOwnedCard, UserProfile, UserUploadedReport
from .views import ConsumptionProfileUpsertView
from .views import OwnedCardUpsertView
from .views import ProfileView


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
