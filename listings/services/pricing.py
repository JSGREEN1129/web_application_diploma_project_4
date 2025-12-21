from decimal import Decimal
from typing import Tuple

from ..models import Listing


def get_return_pct_range(listing: Listing) -> Tuple[Decimal, Decimal]:
    """
    Returns (min_pct, max_pct) as Decimals based on listing.return_band.
    Replace/keep your existing mapping logic here.
    """
    mapping = {
        Listing.ReturnBand.R2_4: (Decimal("2"), Decimal("4")),
        Listing.ReturnBand.R5_9: (Decimal("5"), Decimal("9")),
        Listing.ReturnBand.R10_14: (Decimal("10"), Decimal("14")),
        Listing.ReturnBand.R15_175: (Decimal("15"), Decimal("17.5")),
    }
    if not listing.return_band or listing.return_band not in mapping:
        raise ValueError("Return band is not configured correctly.")
    return mapping[listing.return_band]


def calculate_listing_price_pence(*, funding_band: str, duration_days: int) -> int:
    """
    Calculates upload fee (in pence). Keep your existing logic here.
    """
    if not duration_days or duration_days <= 0:
        raise ValueError("duration_days must be > 0")

    price_per_day_pence = 199
    return int(duration_days) * int(price_per_day_pence)
