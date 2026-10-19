import re
from pathlib import Path

from .model import Bill

PROCESSED_RE = re.compile(
    r"^(NRG|DEI) (gas|revma) \d{4}\.\d{2}\.\d{2} \d+kwh euro -?\d+\.\d{2}( \(\d+\))?\.pdf$"
)


def bill_filename(bill: Bill) -> str:
    return (
        f"{bill.provider} {bill.kind} {bill.issue_date:%Y.%m.%d} "
        f"{bill.kwh}kwh euro {bill.amount:.2f}.pdf"
    )


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
