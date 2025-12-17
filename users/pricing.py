# users/pricing.py

FUNDING_TIER_PENCE = {
    "10000_20000": 1999,
    "21000_30000": 2499,
    "31000_40000": 2999,
    "41000_50000": 3499,
    "51000_75000": 4999,
    "76000_100000": 6499,
    "100000_150000": 8499,
    "151000_250000": 10999,
}

DURATION_TIER_PENCE = {
    7: 499,
    14: 799,
    30: 1299,
    60: 1999,
}

def calculate_listing_price_pence(*, funding_band: str, duration_days: int) -> int:
    if funding_band not in FUNDING_TIER_PENCE:
        raise ValueError("Invalid funding band")
    if duration_days not in DURATION_TIER_PENCE:
        raise ValueError("Invalid duration")
    return FUNDING_TIER_PENCE[funding_band] + DURATION_TIER_PENCE[duration_days]
