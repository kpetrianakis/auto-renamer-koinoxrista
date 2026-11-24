import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

# Ελληνική μορφή αριθμού: 10.954,82 ή -1,03
NUMBER = r"-?[\d.]+,\d{2}"


class ParseError(Exception):
    """Ο λογαριασμός αναγνωρίστηκε, αλλά δεν βρέθηκε κανένα από τα πεδία του."""


def find(pattern: str, text: str) -> str | None:
    """Η πρώτη ομάδα του pattern, ή None αν δεν βρεθεί (το πεδίο μένει κενό)."""
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1) if match else None


def gr_number(value: str) -> Decimal:
    return Decimal(value.replace(".", "").replace(",", "."))


def gr_date(value: str) -> date:
    return datetime.strptime(value, "%d/%m/%Y").date()


def round_kwh(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))
