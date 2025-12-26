from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class ReturnResult:
    expected_return_pence: int
    expected_total_back_pence: int


def calculate_expected_return_pence(*, amount_pence: int, total_return_percent: Decimal) -> ReturnResult:
    """
    total_return_percent is the TOTAL return percent for the opportunity (NOT annualised, NOT pro-rated).
    Uses Decimal math and ROUND_HALF_UP to avoid float rounding issues.
    """
    if amount_pence <= 0:
        return ReturnResult(0, max(amount_pence, 0))

    if total_return_percent <= 0:
        return ReturnResult(0, amount_pence)

    expected_return = (Decimal(amount_pence) * (total_return_percent / Decimal("100"))).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    expected_return_pence = int(expected_return)
    return ReturnResult(expected_return_pence, amount_pence + expected_return_pence)
