from django.conf import settings
from django.db import models
from django.utils import timezone


class Investment(models.Model):
    class Status(models.TextChoices):
        PLEDGED = "pledged", "Pledged"
        CANCELLED = "cancelled", "Cancelled"

    investor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="investments"
    )
    listing = models.ForeignKey(
        "users.Listing", on_delete=models.CASCADE, related_name="investments"
    )

    amount_pence = models.PositiveIntegerField()
    expected_return_pence = models.PositiveIntegerField(default=0)
    expected_total_back_pence = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLEDGED)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["listing", "status"]),
            models.Index(fields=["investor", "status"]),
        ]

    def __str__(self):
        return f"{self.investor_id} -> {self.listing_id} (£{self.amount_pence/100:.2f})"
