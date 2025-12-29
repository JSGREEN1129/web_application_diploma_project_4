from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class ReturnResult:
    # Container for calculated return values
    expected_return_pence: int
    expected_total_back_pence: int


def calculate_expected_return_pence(*, amount_pence: int, total_return_percent: Decimal) -> ReturnResult:
    """
    Calculate expected return values in pence.

    - total_return_percent is the TOTAL return for the opportunity
      (not annualised and not pro-rated).
    - Uses Decimal math with ROUND_HALF_UP to avoid floating point issues.
    """

    # Guard against zero or negative investment amounts
    if amount_pence <= 0:
        return ReturnResult(0, max(amount_pence, 0))

    # Guard against zero or negative return percentages
    if total_return_percent <= 0:
        return ReturnResult(0, amount_pence)

    # Calculate expected return in pence using Decimal arithmetic
    expected_return = (
        Decimal(amount_pence) * (total_return_percent / Decimal("100"))
    ).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )

    expected_return_pence = int(expected_return)

    # Total amount returned = original amount and expected return
    return ReturnResult(
        expected_return_pence,
        amount_pence + expected_return_pence,
    )
