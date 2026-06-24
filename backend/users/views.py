from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.db import transaction
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.card_catalog import card_image_url
from finance.models import CardProduct, CardType, ParseStatus
from .models import UserProfile
from .models import UserConsumptionProfile
from .models import UserOwnedCard
from .models import UserUploadedReport

import hashlib


User = get_user_model()


def _frontend_profile(user):
    if not user or not user.is_authenticated:
        return {
            "name": "김슬픽",
            "email": "seulpick@example.com",
            "ownedCards": [],
            "monthlySpend": 800000,
        }
    owned_cards = list(user.owned_cards.select_related("card").prefetch_related("card__images"))
    return {
        "id": user.id,
        "username": user.username,
        "name": user.first_name or user.username,
        "email": user.email,
        "ownedCards": [owned.card.name for owned in owned_cards],
        "ownedCardDetails": [
            {
                "id": owned.card.id,
                "name": owned.card.name,
                "issuer": owned.card.issuer,
                "type": owned.card.card_type,
                "card_type": owned.card.card_type,
                "image_url": card_image_url(owned.card),
                "source_url": owned.card.source_url,
                "is_manual": owned.card.source_channel == "manual_user",
            }
            for owned in owned_cards
        ],
        "monthlySpend": 800000,
    }


@api_view(["POST"])
def login_view(request):
    username = (request.data.get("username") or request.data.get("email") or "").strip()
    password = request.data.get("password") or ""
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"error": "아이디 또는 비밀번호가 올바르지 않습니다."}, status=400)
    auth_login(request, user)
    return Response({"authenticated": True, "profile": _frontend_profile(user)})


@api_view(["GET"])
@ensure_csrf_cookie
def auth_status_view(request):
    if not request.user.is_authenticated:
        return Response({"authenticated": False, "profile": None})
    return Response({"authenticated": True, "profile": _frontend_profile(request.user)})


@api_view(["POST"])
def register_view(request):
    username = (request.data.get("username") or request.data.get("email") or "").strip()
    password = request.data.get("password") or ""
    name = (request.data.get("name") or username).strip()
    email = (request.data.get("email") or "").strip()
    if not username or not password:
        return Response({"error": "아이디와 비밀번호를 입력해주세요."}, status=400)
    if User.objects.filter(username=username).exists():
        return Response({"error": "이미 존재하는 아이디입니다."}, status=400)
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        first_name=name,
    )
    auth_login(request, user)
    return Response({"authenticated": True, "profile": _frontend_profile(user)})


@api_view(["POST"])
def logout_view(request):
    auth_logout(request)
    return Response({"authenticated": False, "profile": _frontend_profile(request.user)})


@api_view(["POST"])
def update_profile_view(request):
    if not request.user.is_authenticated:
        return Response({"error": "로그인이 필요합니다."}, status=401)
    request.user.first_name = (
        request.data.get("name") or request.user.first_name or request.user.username
    ).strip()
    request.user.email = (request.data.get("email") or request.user.email).strip()
    password = request.data.get("password") or ""
    if password:
        request.user.set_password(password)
    request.user.save()
    if password:
        auth_login(request, request.user)
    return Response({"profile": _frontend_profile(request.user)})


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
        user = profile.user if profile else User.objects.order_by("id").first()
        if user:
            owned_cards = [
                {
                    "id": owned.card_id,
                    "name": owned.card.name,
                    "issuer": owned.card.issuer,
                    "type": owned.card.card_type,
                    "card_type": owned.card.card_type,
                    "image_url": card_image_url(owned.card),
                    "source_url": owned.card.source_url,
                    "is_manual": owned.card.source_channel == "manual_user",
                }
                for owned in user.owned_cards.all()
                .select_related("card")
                .prefetch_related("card__images")
            ]
            latest_report = (
                user.uploaded_reports.order_by("-created_at")
                .values("file_url", "file_type", "parse_status")
                .first()
            )
            consumption_profile = getattr(user, "consumption_profile", None)
            return Response(
                {
                    "username": user.get_username(),
                    "nickname": profile.nickname if profile else "",
                    "home_address": profile.preferred_area if profile else "",
                    "monthly_expected_spend": (
                        profile.monthly_expected_spend if profile else 0
                    ),
                    "favorite_cards": owned_cards,
                    "ownedCardDetails": owned_cards,
                    "uploaded_report": latest_report,
                    "consumption_profile": (
                        {
                            "source": consumption_profile.source,
                            "is_cold_start": consumption_profile.is_cold_start,
                            "spending_json": consumption_profile.spending_json,
                            "last_updated_at": consumption_profile.last_updated_at.isoformat(),
                        }
                        if consumption_profile
                        else None
                    ),
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
                "consumption_profile": None,
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
        remove_card_ids = request.data.get("remove_card_ids") or []
        manual_card_names = request.data.get("manual_card_names") or []
        if not isinstance(card_ids, list):
            return Response({"detail": "card_ids는 리스트여야 합니다."}, status=400)
        if not isinstance(remove_card_ids, list):
            return Response({"detail": "remove_card_ids must be a list"}, status=400)
        if isinstance(manual_card_names, str):
            manual_card_names = [manual_card_names]
        if not isinstance(manual_card_names, list):
            return Response({"detail": "manual_card_names는 리스트여야 합니다."}, status=400)
        removed = UserOwnedCard.objects.filter(
            user=user,
            card_id__in=remove_card_ids,
        ).delete()[0]
        created = 0
        for card_id in card_ids:
            card = CardProduct.objects.get(pk=card_id)
            _, is_created = UserOwnedCard.objects.get_or_create(user=user, card=card)
            created += int(is_created)
        for raw_name in manual_card_names:
            name = str(raw_name or "").strip()
            if not name:
                continue
            digest = hashlib.sha1(f"{user.id}:{name}".encode("utf-8")).hexdigest()[:16]
            card, _ = CardProduct.objects.get_or_create(
                source_channel="manual_user",
                external_id=f"user-{user.id}-{digest}",
                defaults={
                    "issuer": "수동 추가",
                    "provider": "수동 추가",
                    "card_type": CardType.CREDIT,
                    "name": name,
                    "source_url": f"https://manual.seulpick.local/cards/{user.id}-{digest}",
                    "annual_fee": None,
                    "previous_month_requirement": 0,
                    "monthly_discount_limit": None,
                    "parse_status": ParseStatus.INACTIVE,
                    "raw_text": "사용자가 프로필에서 수동으로 추가한 보유카드입니다.",
                },
            )
            _, is_created = UserOwnedCard.objects.get_or_create(user=user, card=card)
            created += int(is_created)
        return Response(
            {
                "user_id": user.id,
                "card_ids": card_ids,
                "remove_card_ids": remove_card_ids,
                "manual_card_names": manual_card_names,
                "created_count": created,
                "removed_count": removed,
                "profile": _frontend_profile(user),
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
        parsed_payload = request.data.get("parsed_payload", {})
        report = UserUploadedReport.objects.create(
            user=user,
            file_url=request.data["file_url"],
            file_type=request.data.get("file_type", ""),
            parse_status=request.data.get("parse_status", "raw"),
            parsed_payload=parsed_payload,
        )
        spending = parsed_payload.get("spending") if isinstance(parsed_payload, dict) else None
        if isinstance(spending, dict):
            UserConsumptionProfile.objects.update_or_create(
                user=user,
                defaults={
                    "source": "image_parser",
                    "spending_json": spending,
                    "is_cold_start": False,
                },
            )
        return Response(
            {
                "id": report.id,
                "user_id": user.id,
                "file_url": report.file_url,
                "file_type": report.file_type,
                "parse_status": report.parse_status,
                "consumption_profile_updated": isinstance(spending, dict),
            },
            status=201,
        )
