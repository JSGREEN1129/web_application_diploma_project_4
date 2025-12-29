from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils import timezone


class Investment(models.Model):
    class Status(models.TextChoices):
        # Investment lifecycle states
        PLEDGED = "pledged", "Pledged"
        CANCELLED = "cancelled", "Cancelled"

    # User making the investment
    investor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="investments",
    )

    # Listing the investment relates to
    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.CASCADE,
        related_name="investments",
    )

    # Stored in pence to avoid floating point issues
    amount_pence = models.PositiveIntegerField()
    expected_return_pence = models.PositiveIntegerField(default=0)
    expected_total_back_pence = models.PositiveIntegerField(default=0)

    # Current status of the investment
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLEDGED,
    )

    # Timestamp for when the pledge was created
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        # Indexes to optimise common dashboard and listing queries
        indexes = [
            models.Index(fields=["listing", "status"]),
            models.Index(fields=["investor", "status"]),
        ]

    @staticmethod
    def _pence_to_gbp(pence: int) -> Decimal:
        # Convert integer pence to Decimal GBP, rounded to 2dp
        return (Decimal(pence) / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def amount_gbp(self) -> Decimal:
        # Amount pledged in GBP
        return self._pence_to_gbp(self.amount_pence)

    @property
    def expected_return_gbp(self) -> Decimal:
        # Expected profit
        return self._pence_to_gbp(self.expected_return_pence)

    @property
    def expected_total_back_gbp(self) -> Decimal:
        # Expected total returned
        return self._pence_to_gbp(self.expected_total_back_pence)

    def __str__(self):
        # Human-readable identifier for admin/debugging
        return f"{self.investor_id} -> {self.listing_id} (£{self.amount_gbp})"
