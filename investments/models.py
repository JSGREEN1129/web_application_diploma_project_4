from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils import timezone


class Investment(models.Model):
    class Status(models.TextChoices):
        PLEDGED = "pledged", "Pledged"
        CANCELLED = "cancelled", "Cancelled"

    investor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="investments",
    )
    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.CASCADE,
        related_name="investments",
    )

    amount_pence = models.PositiveIntegerField()
    expected_return_pence = models.PositiveIntegerField(default=0)
    expected_total_back_pence = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLEDGED,
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["listing", "status"]),
            models.Index(fields=["investor", "status"]),
        ]

    @staticmethod
    def _pence_to_gbp(pence: int) -> Decimal:
        return (Decimal(pence) / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def amount_gbp(self) -> Decimal:
        return self._pence_to_gbp(self.amount_pence)

    @property
    def expected_return_gbp(self) -> Decimal:
        return self._pence_to_gbp(self.expected_return_pence)

    @property
    def expected_total_back_gbp(self) -> Decimal:
        return self._pence_to_gbp(self.expected_total_back_pence)

    def __str__(self):
        return f"{self.investor_id} -> {self.listing_id} (£{self.amount_gbp})"
