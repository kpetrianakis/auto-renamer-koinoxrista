import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

# Ελληνική μορφή αριθμού: 10.954,82 ή -1,03
NUMBER = r"-?[\d.]+,\d{2}"


class ParseError(Exception):
    """Ο λογαριασμός αναγνωρίστηκε, αλλά λείπει κάποιο πεδίο."""


def find(pattern: str, text: str, what: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        raise ParseError(f"δεν βρέθηκε: {what}")
    return match.group(1)


def gr_number(value: str) -> Decimal:
    return Decimal(value.replace(".", "").replace(",", "."))


def gr_date(value: str) -> date:
    return datetime.strptime(value, "%d/%m/%Y").date()


def round_kwh(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))
