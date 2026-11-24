from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# Ονόματα πεδίων για τα μηνύματα του log
FIELD_LABELS = {"issue_date": "ημερομηνία έκδοσης", "kwh": "kWh", "amount": "σύνολο λογαριασμού"}


@dataclass(frozen=True)
class Bill:
    provider: str  # "NRG" | "DEI"
    kind: str  # "gas" | "revma"
    issue_date: date | None  # None = δεν βρέθηκε στο PDF, μένει κενό στο όνομα
    kwh: int | None
    amount: Decimal | None

    def missing(self) -> list[str]:
        return [label for field, label in FIELD_LABELS.items() if getattr(self, field) is None]
