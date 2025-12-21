from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Listing(models.Model):
    class UseType(models.TextChoices):
        COMMERCIAL = "commercial", "Commercial"
        RESIDENTIAL = "residential", "Residential"
        INDUSTRIAL = "industrial", "Industrial"

    class Country(models.TextChoices):
        ENGLAND = "england", "England"
        SCOTLAND = "scotland", "Scotland"
        WALES = "wales", "Wales"

    class ReturnType(models.TextChoices):
        EQUITY = "equity_share", "Equity Share"
        PAYBACK = "financial_payback", "Financial Payback"

    class FundingBand(models.TextChoices):
        B10_20 = "10000_20000", "£10,000 - £20,000"
        B21_30 = "21000_30000", "£21,000 - £30,000"
        B31_40 = "31000_40000", "£31,000 - £40,000"
        B41_50 = "41000_50000", "£41,000 - £50,000"
        B51_75 = "51000_75000", "£51,000 - £75,000"
        B76_100 = "76000_100000", "£76,000 - £100,000"
        B100_150 = "100000_150000", "£100,000 - £150,000"
        B151_250 = "151000_250000", "£151,000 - £250,000"

    class ReturnBand(models.TextChoices):
        R2_4 = "2_4", "2% - 4%"
        R5_9 = "5_9", "5% - 9%"
        R10_14 = "10_14", "10% - 14%"
        R15_175 = "15_17_5", "15% - 17.5%"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_PAYMENT = "pending_payment", "Pending payment"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="listings",
    )

    project_name = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Optional project name shown in dashboards and opportunities (e.g. Old Police Station).",
    )

    source_use = models.CharField(
        max_length=20,
        choices=UseType.choices,
        blank=True,
        null=True,
    )
    target_use = models.CharField(
        max_length=20,
        choices=UseType.choices,
        blank=True,
        null=True,
    )

    country = models.CharField(
        max_length=20,
        choices=Country.choices,
        blank=True,
        null=True,
    )
    county = models.CharField(
        max_length=64,
        blank=True,
        null=True,
    )
    postcode_prefix = models.CharField(
        max_length=10,
        blank=True,
        null=True,
    )

    funding_band = models.CharField(
        max_length=20,
        choices=FundingBand.choices,
        blank=True,
        null=True,
    )
    return_type = models.CharField(
        max_length=30,
        choices=ReturnType.choices,
        blank=True,
        null=True,
    )
    return_band = models.CharField(
        max_length=20,
        choices=ReturnBand.choices,
        blank=True,
        null=True,
    )

    duration_days = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="How long the listing stays active to secure funding (days).",
    )

    project_duration_days = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="How long the underlying project is expected to run (days).",
    )

    price_per_day_pence = models.PositiveIntegerField(default=199)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    active_from = models.DateTimeField(null=True, blank=True)
    active_until = models.DateTimeField(null=True, blank=True)

    expected_amount_pence = models.PositiveIntegerField(default=0)
    paid_amount_pence = models.PositiveIntegerField(default=0)
    paid_at = models.DateTimeField(null=True, blank=True)

    stripe_checkout_session_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    def listing_active_days(self) -> int:
        """Safe int value for listing active duration."""
        return int(self.duration_days or 0)

    def project_days(self) -> int:
        """Safe int value for project duration."""
        return int(self.project_duration_days or 0)

    def total_price_pence(self) -> int:
        """
        Listing upload fee. For drafts, duration_days may be None; keep this safe.
        """
        if not self.duration_days:
            return 0
        return int(self.duration_days) * int(self.price_per_day_pence)

    def activate(self) -> None:
        """
        Activate the listing. This uses duration_days (listing active duration),
        NOT project_duration_days (project term).
        """
        if not self.duration_days:
            raise ValueError("Cannot activate listing without duration_days.")

        now = timezone.now()
        self.status = self.Status.ACTIVE
        self.active_from = now
        self.active_until = now + timedelta(days=int(self.duration_days))
        self.save(update_fields=["status", "active_from", "active_until"])

    def __str__(self) -> str:
        name = self.project_name.strip() if self.project_name else ""
        label = name or f"Listing {self.pk}"
        return f"{label} ({self.get_status_display()})"


def listing_media_upload_to(instance: "ListingMedia", filename: str) -> str:
    return f"listing_media/listing_{instance.listing_id}/{filename}"


class ListingMedia(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        DOCUMENT = "document", "Document"

    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="media",
    )

    file = models.FileField(upload_to=listing_media_upload_to)
    media_type = models.CharField(
        max_length=20,
        choices=MediaType.choices,
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.media_type} for listing {self.listing_id}"
