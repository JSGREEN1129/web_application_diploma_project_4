# users/services.py
from django.utils import timezone
from django.db.models import Q

from .models import Listing


def expire_due_listings() -> int:
    now = timezone.now()

    updated = (
        Listing.objects
        .filter(status=Listing.Status.ACTIVE)
        .filter(active_until__isnull=False, active_until__lte=now)
        .update(status=Listing.Status.EXPIRED)
    )
    return updated
