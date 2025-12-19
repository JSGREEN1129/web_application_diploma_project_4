from dataclasses import dataclass


@dataclass(frozen=True)
class ReturnResult:
    expected_return_pence: int
    expected_total_back_pence: int


def calculate_expected_return_pence(*, amount_pence: int, total_return_percent: float) -> ReturnResult:
 
    if amount_pence <= 0 or total_return_percent <= 0:
        return ReturnResult(0, max(amount_pence, 0))

    expected_return = int(round(amount_pence * (total_return_percent / 100.0)))
    return ReturnResult(expected_return, amount_pence + expected_return)
