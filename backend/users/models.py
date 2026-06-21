from django.conf import settings
from django.db import models
from django.utils import timezone

from finance.models import CardProduct, ParseStatus


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="seulpick_profile",
        on_delete=models.CASCADE,
    )
    nickname = models.CharField(max_length=50, blank=True)
    preferred_area = models.CharField(max_length=255, blank=True)
    monthly_expected_spend = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user_id"]

    def __str__(self):
        return f"{self.user_id}:{self.nickname or self.user.get_username()}"


class UserOwnedCard(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="owned_cards",
        on_delete=models.CASCADE,
    )
    card = models.ForeignKey(
        CardProduct,
        related_name="owned_by_users",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user_id", "card_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "card"],
                name="unique_user_owned_card",
            )
        ]

    def __str__(self):
        return f"{self.user_id}:{self.card_id}"


class UserConsumptionProfile(models.Model):
    source_choices = [
        ("user", "user"),
        ("mydata", "mydata"),
        ("image_parser", "image_parser"),
        ("cohort_default", "cohort_default"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="consumption_profile",
        on_delete=models.CASCADE,
    )
    source = models.CharField(max_length=50, choices=source_choices)
    spending_json = models.JSONField(default=dict, blank=True)
    is_cold_start = models.BooleanField(default=False)
    last_updated_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user_id"]

    def __str__(self):
        return f"{self.user_id}:{self.source}"


class UserUploadedReport(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="uploaded_reports",
        on_delete=models.CASCADE,
    )
    file_url = models.URLField(max_length=1000)
    file_type = models.CharField(max_length=100, blank=True)
    parse_status = models.CharField(
        max_length=20,
        choices=ParseStatus.choices,
        default=ParseStatus.RAW,
    )
    parsed_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id}:{self.file_type or 'report'}"
