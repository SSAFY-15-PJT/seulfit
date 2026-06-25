from django.db import models
from django.utils import timezone


class CrawlStatus(models.TextChoices):
    PENDING = "pending", "대기"
    FETCHING = "fetching", "수집 중"
    SUCCESS = "success", "성공"
    RETRY_PENDING = "retry_pending", "재시도 대기"
    PAUSED = "paused", "일시 중단"
    FAILED = "failed", "실패"


class ParseStatus(models.TextChoices):
    RAW = "raw", "원본"
    NORMALIZED = "normalized", "정규화"
    VALIDATED = "validated", "검증 완료"
    ACTIVE = "active", "추천 사용"
    REVIEW_REQUIRED = "review_required", "검토 필요"
    INVALID = "invalid", "유효하지 않음"
    INACTIVE = "inactive", "비활성"


class Category(models.Model):
    key = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=100)
    kakao_code = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.label


class CardType(models.TextChoices):
    CREDIT = "credit", "신용카드"
    DEBIT = "debit", "체크카드"


class DiscountType(models.TextChoices):
    RATE = "rate", "비율"
    AMOUNT = "amount", "정액"


class CrawlJob(models.Model):
    source_channel = models.CharField(max_length=50, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=CrawlStatus.choices,
        default=CrawlStatus.PENDING,
        db_index=True,
    )
    resume_cursor = models.JSONField(default=dict, blank=True)
    total_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    last_checkpoint_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.source_channel}:{self.pk}:{self.status}"


class CrawlItem(models.Model):
    job = models.ForeignKey(CrawlJob, related_name="items", on_delete=models.CASCADE)
    external_id = models.CharField(max_length=255, blank=True)
    source_url = models.URLField(max_length=1000)
    status = models.CharField(
        max_length=20,
        choices=CrawlStatus.choices,
        default=CrawlStatus.PENDING,
        db_index=True,
    )
    retry_count = models.PositiveSmallIntegerField(default=0)
    raw_payload = models.JSONField(default=dict, blank=True)
    last_error = models.TextField(blank=True)
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "source_url"],
                name="unique_crawl_item_url_per_job",
            )
        ]

    def __str__(self):
        return f"{self.job.source_channel}:{self.source_url}:{self.status}"


class CardProduct(models.Model):
    external_id = models.CharField(max_length=255)
    issuer = models.CharField(max_length=100)
    provider = models.CharField(max_length=100)
    source_channel = models.CharField(max_length=50, db_index=True)
    card_type = models.CharField(max_length=10, choices=CardType.choices)
    name = models.CharField(max_length=255)
    source_url = models.URLField(max_length=1000)
    annual_fee = models.PositiveIntegerField(null=True, blank=True)
    annual_fee_source_url = models.URLField(max_length=1000, blank=True)
    annual_fee_verified_at = models.DateTimeField(null=True, blank=True)
    previous_month_requirement = models.PositiveIntegerField(default=0)
    monthly_discount_limit = models.PositiveIntegerField(null=True, blank=True)
    parse_status = models.CharField(
        max_length=20,
        choices=ParseStatus.choices,
        default=ParseStatus.RAW,
        db_index=True,
    )
    raw_text = models.TextField()
    validation_errors = models.JSONField(default=list, blank=True)
    review_reasons = models.JSONField(default=list, blank=True)
    collected_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["issuer", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_channel", "external_id"],
                name="unique_card_external_id_per_source",
            )
        ]

    def __str__(self):
        return f"{self.issuer} {self.name}"


class BenefitRule(models.Model):
    card = models.ForeignKey(
        CardProduct,
        related_name="benefits",
        on_delete=models.CASCADE,
    )
    category = models.CharField(max_length=50)
    benefit_group = models.CharField(max_length=100, blank=True)
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices)
    discount_rate = models.DecimalField(
        max_digits=7,
        decimal_places=6,
        null=True,
        blank=True,
    )
    discount_amount = models.PositiveIntegerField(null=True, blank=True)
    minimum_transaction_amount = models.PositiveIntegerField(default=0)
    maximum_transaction_amount = models.PositiveIntegerField(null=True, blank=True)
    per_transaction_limit = models.PositiveIntegerField(null=True, blank=True)
    daily_benefit_limit = models.PositiveIntegerField(null=True, blank=True)
    daily_usage_limit = models.PositiveIntegerField(null=True, blank=True)
    monthly_usage_limit = models.PositiveIntegerField(null=True, blank=True)
    estimated_monthly_uses = models.PositiveIntegerField(null=True, blank=True)
    category_monthly_limit = models.PositiveIntegerField(null=True, blank=True)
    merchant_scope = models.JSONField(default=list, blank=True)
    channel = models.CharField(max_length=10, default="all")
    start_hour = models.PositiveSmallIntegerField(null=True, blank=True)
    end_hour = models.PositiveSmallIntegerField(null=True, blank=True)
    condition_text = models.TextField(blank=True)
    exclusion_text = models.TextField(blank=True)
    raw_text = models.TextField()
    parse_status = models.CharField(
        max_length=20,
        choices=ParseStatus.choices,
        default=ParseStatus.RAW,
        db_index=True,
    )
    unsupported_conditions = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["card_id", "pk"]

    def __str__(self):
        return f"{self.card.name}:{self.category}:{self.discount_type}"


class CardBenefitTier(models.Model):
    card = models.ForeignKey(
        CardProduct,
        related_name="benefit_tiers",
        on_delete=models.CASCADE,
    )
    scope = models.CharField(max_length=100, default="card_total")
    minimum_spending = models.PositiveIntegerField()
    maximum_spending = models.PositiveIntegerField(null=True, blank=True)
    monthly_discount_limit = models.PositiveIntegerField()
    raw_text = models.TextField()
    parse_status = models.CharField(
        max_length=20,
        choices=ParseStatus.choices,
        default=ParseStatus.VALIDATED,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["card_id", "scope", "minimum_spending"]
        constraints = [
            models.UniqueConstraint(
                fields=["card", "scope", "minimum_spending"],
                name="unique_card_benefit_tier_minimum",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(maximum_spending__isnull=True)
                    | models.Q(maximum_spending__gt=models.F("minimum_spending"))
                ),
                name="benefit_tier_max_greater_than_min",
            ),
        ]

    def __str__(self):
        return (
            f"{self.card.name}:{self.scope}:"
            f"{self.minimum_spending}-{self.maximum_spending}"
        )


class CardServiceLimitTier(models.Model):
    card = models.ForeignKey(
        CardProduct,
        related_name="service_limit_tiers",
        on_delete=models.CASCADE,
    )
    benefit_group = models.CharField(max_length=100)
    minimum_spending = models.PositiveIntegerField()
    maximum_spending = models.PositiveIntegerField(null=True, blank=True)
    monthly_spending_limit = models.PositiveIntegerField(null=True, blank=True)
    monthly_discount_limit = models.PositiveIntegerField(null=True, blank=True)
    monthly_usage_limit = models.PositiveIntegerField(null=True, blank=True)
    raw_text = models.TextField()
    parse_status = models.CharField(
        max_length=20,
        choices=ParseStatus.choices,
        default=ParseStatus.VALIDATED,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["card_id", "benefit_group", "minimum_spending"]
        constraints = [
            models.UniqueConstraint(
                fields=["card", "benefit_group", "minimum_spending"],
                name="unique_card_service_limit_tier",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(maximum_spending__isnull=True)
                    | models.Q(maximum_spending__gt=models.F("minimum_spending"))
                ),
                name="service_limit_tier_max_greater_than_min",
            ),
        ]


class CardImage(models.Model):
    card = models.ForeignKey(
        CardProduct,
        related_name="images",
        on_delete=models.CASCADE,
    )
    source_url = models.URLField(max_length=1000)
    local_path = models.CharField(max_length=1000, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    checksum = models.CharField(max_length=80, blank=True)
    download_status = models.CharField(
        max_length=20,
        choices=CrawlStatus.choices,
        default=CrawlStatus.PENDING,
    )
    is_primary = models.BooleanField(default=False)
    alt_text = models.CharField(max_length=500, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["card_id", "-is_primary", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["card", "source_url"],
                name="unique_card_image_source",
            )
        ]


class CrawlSnapshot(models.Model):
    crawl_item = models.ForeignKey(
        CrawlItem,
        related_name="snapshots",
        on_delete=models.CASCADE,
    )
    card = models.ForeignKey(
        CardProduct,
        related_name="snapshots",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    source_url = models.URLField(max_length=1000)
    raw_html = models.TextField()
    content_checksum = models.CharField(max_length=80)
    collected_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-collected_at"]
