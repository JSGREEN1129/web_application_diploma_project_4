from dataclasses import dataclass


@dataclass(frozen=True)
class ReturnResult:
    expected_return_pence: int
    expected_total_back_pence: int


def calculate_expected_return_pence(*, amount_pence: int, apr_percent: float, duration_days: int) -> ReturnResult:
    if amount_pence <= 0 or apr_percent <= 0 or duration_days <= 0:
        return ReturnResult(0, max(amount_pence, 0))

    years = duration_days / 365.0
    expected_return = int(round(amount_pence * (apr_percent / 100.0) * years))
    return ReturnResult(expected_return, amount_pence + expected_return)
