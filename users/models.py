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

    source_use = models.CharField(max_length=20, choices=UseType.choices)
    target_use = models.CharField(max_length=20, choices=UseType.choices)

    country = models.CharField(max_length=20, choices=Country.choices)
    county = models.CharField(max_length=64)
    postcode_prefix = models.CharField(max_length=10)

    funding_band = models.CharField(max_length=20, choices=FundingBand.choices)
    return_type = models.CharField(max_length=30, choices=ReturnType.choices)
    return_band = models.CharField(max_length=20, choices=ReturnBand.choices)

    duration_days = models.PositiveIntegerField()

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

    def total_price_pence(self) -> int:
        return self.duration_days * self.price_per_day_pence

    def activate(self):
        now = timezone.now()
        self.status = self.Status.ACTIVE
        self.active_from = now
        self.active_until = now + timezone.timedelta(days=self.duration_days)
        self.save(update_fields=["status", "active_from", "active_until"])


def listing_media_upload_to(instance, filename):
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

    def __str__(self):
        return f"{self.media_type} for listing {self.listing.id}"
