from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.models import CardProduct
from .models import UserProfile
from .models import UserConsumptionProfile
from .models import UserOwnedCard
from .models import UserUploadedReport


User = get_user_model()


def _resolve_user(payload):
    user_id = payload.get("user_id")
    if user_id:
        return User.objects.get(pk=user_id)

    email = payload.get("email")
    username = payload.get("username") or (email.split("@", 1)[0] if email else None)
    password = payload.get("password")
    if not email or not username or not password:
        raise ValueError("user_id 또는 email/username/password가 필요합니다.")

    user, created = User.objects.get_or_create(
        username=username,
        defaults={"email": email},
    )
    if email and user.email != email:
        user.email = email
    if password:
        user.set_password(password)
    user.save()
    return user


class ProfileView(APIView):
    def get(self, request):
        profile = (
            UserProfile.objects.select_related("user")
            .order_by("user_id")
            .first()
        )
        if profile:
            owned_cards = [
                {
                    "id": owned.card_id,
                    "name": owned.card.name,
                    "issuer": owned.card.issuer,
                    "image_url": (
                        owned.card.images.filter(is_primary=True)
                        .values_list("source_url", flat=True)
                        .first()
                        or ""
                    ),
                }
                for owned in profile.user.owned_cards.all().select_related("card")
            ]
            latest_report = (
                profile.user.uploaded_reports.order_by("-created_at")
                .values("file_url", "file_type", "parse_status")
                .first()
            )
            return Response(
                {
                    "username": profile.user.get_username(),
                    "nickname": profile.nickname,
                    "home_address": profile.preferred_area,
                    "monthly_expected_spend": profile.monthly_expected_spend,
                    "favorite_cards": owned_cards,
                    "uploaded_report": latest_report,
                }
            )

        return Response(
            {
                "username": "seulpick-demo",
                "nickname": "게스트",
                "home_address": "서울 강남구",
                "monthly_expected_spend": 0,
                "favorite_cards": [],
                "uploaded_report": None,
            }
        )

    @transaction.atomic
    def post(self, request):
        user = _resolve_user(request.data)
        profile, _ = UserProfile.objects.update_or_create(
            user=user,
            defaults={
                "nickname": request.data.get("nickname", ""),
                "preferred_area": request.data.get("preferred_area", ""),
                "monthly_expected_spend": request.data.get(
                    "monthly_expected_spend", 0
                ),
            },
        )
        return Response(
            {
                "user_id": user.id,
                "nickname": profile.nickname,
                "preferred_area": profile.preferred_area,
                "monthly_expected_spend": profile.monthly_expected_spend,
            }
        )


class OwnedCardUpsertView(APIView):
    @transaction.atomic
    def post(self, request):
        user = _resolve_user(request.data)
        card_ids = request.data.get("card_ids") or []
        if not isinstance(card_ids, list):
            return Response({"detail": "card_ids는 리스트여야 합니다."}, status=400)
        created = 0
        for card_id in card_ids:
            card = CardProduct.objects.get(pk=card_id)
            _, is_created = UserOwnedCard.objects.get_or_create(user=user, card=card)
            created += int(is_created)
        return Response(
            {
                "user_id": user.id,
                "card_ids": card_ids,
                "created_count": created,
            }
        )


class ConsumptionProfileUpsertView(APIView):
    @transaction.atomic
    def post(self, request):
        user = _resolve_user(request.data)
        profile, _ = UserConsumptionProfile.objects.update_or_create(
            user=user,
            defaults={
                "source": request.data.get("source", "user"),
                "spending_json": request.data.get("spending_json", {}),
                "is_cold_start": bool(request.data.get("is_cold_start", False)),
            },
        )
        return Response(
            {
                "user_id": user.id,
                "source": profile.source,
                "is_cold_start": profile.is_cold_start,
                "spending_json": profile.spending_json,
            }
        )


class UploadedReportCreateView(APIView):
    @transaction.atomic
    def post(self, request):
        user = _resolve_user(request.data)
        report = UserUploadedReport.objects.create(
            user=user,
            file_url=request.data["file_url"],
            file_type=request.data.get("file_type", ""),
            parse_status=request.data.get("parse_status", "raw"),
            parsed_payload=request.data.get("parsed_payload", {}),
        )
        return Response(
            {
                "id": report.id,
                "user_id": user.id,
                "file_url": report.file_url,
                "file_type": report.file_type,
                "parse_status": report.parse_status,
            },
            status=201,
        )
