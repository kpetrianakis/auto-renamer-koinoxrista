from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Bill:
    provider: str  # "NRG" | "DEI"
    kind: str  # "gas" | "revma"
    issue_date: date
    kwh: int
    amount: Decimal
