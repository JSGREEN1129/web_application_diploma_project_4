# users/services.py
from django.utils import timezone
from django.db.models import Q

from .models import Listing


def expire_due_listings() -> int:
    """
    Expire active listings whose active period has ended.

    Returns:
        int: Number of listings updated.
    """
    # Current timestamp for comparison
    now = timezone.now()

    # Update all active listings that have an end date in the past
    updated = (
        Listing.objects
        .filter(status=Listing.Status.ACTIVE)
        .filter(active_until__isnull=False, active_until__lte=now)
        .update(status=Listing.Status.EXPIRED)
    )

    # Return the count of updated records
    return updated
