import re
from pathlib import Path

from .model import Bill

# Κάθε πεδίο μπορεί να είναι κενό (δεν βρέθηκε στο PDF): και τότε το όνομα
# πρέπει να αναγνωρίζεται ως επεξεργασμένο, αλλιώς ατέρμονες μετονομασίες.
PROCESSED_RE = re.compile(
    r"^(NRG|DEI) (gas|revma) (\d{4}\.\d{2}\.\d{2})? (\d+)?kwh euro (-?\d+\.\d{2})?( \(\d+\))?\.pdf$"
)


def bill_filename(bill: Bill) -> str:
    issue_date = f"{bill.issue_date:%Y.%m.%d}" if bill.issue_date is not None else ""
    kwh = str(bill.kwh) if bill.kwh is not None else ""
    amount = f"{bill.amount:.2f}" if bill.amount is not None else ""
    return f"{bill.provider} {bill.kind} {issue_date} {kwh}kwh euro {amount}.pdf"


def is_processed(name: str) -> bool:
    return PROCESSED_RE.match(name) is not None


def unique_path(directory: Path, filename: str) -> Path:
    """Ελεύθερο όνομα στον φάκελο· ποτέ δεν επιστρέφει υπάρχον αρχείο."""
    candidate = directory / filename
    stem, suffix = candidate.stem, candidate.suffix
    n = 2
    while candidate.exists():
        candidate = directory / f"{stem} ({n}){suffix}"
        n += 1
    return candidate
