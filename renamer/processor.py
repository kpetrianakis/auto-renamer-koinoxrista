from dataclasses import dataclass
from pathlib import Path

from .config import FOLDER_KINDS
from .naming import bill_filename, is_processed, unique_path
from .parsers import ParseError, parse_bill
from .pdftext import extract_text


@dataclass(frozen=True)
class Result:
    # renamed | would_rename | skipped | unrecognized | error | locked
    status: str
    source: Path
    target: Path | None = None
    message: str = ""


def process_file(path: Path, *, dry_run: bool = False) -> Result:
    if path.suffix.lower() != ".pdf" or is_processed(path.name):
        return Result("skipped", path)

    try:
        text = extract_text(path)
    except Exception as exc:  # κλειδωμένο από OneDrive ή μισογραμμένο: ξαναδοκιμάζεται
        return Result("locked", path, message=f"ανάγνωση PDF: {exc}")
    if not text.strip():  # μισογραμμένο αρχείο που «επισκευάστηκε» σε κενό έγγραφο
        return Result("locked", path, message="το PDF δεν έχει (ακόμα) κείμενο")

    try:
        bill = parse_bill(text)
    except ParseError as exc:
        return Result("error", path, message=str(exc))
    if bill is None:
        return Result("unrecognized", path)

    message = ""
    expected_kind = FOLDER_KINDS.get(path.parent.name)
    if expected_kind and expected_kind != bill.kind:
        message = f"λογαριασμός «{bill.kind}» στον φάκελο «{path.parent.name}»"

    filename = bill_filename(bill)
    if not is_processed(filename):  # αλλιώς ο watcher θα το ξαναμετονόμαζε επ' άπειρον
        return Result("error", path, message=f"μη έγκυρο όνομα: {filename}")
    target = unique_path(path.parent, filename)
    if dry_run:
        return Result("would_rename", path, target, message)
    try:
        path.rename(target)  # στα Windows αποτυγχάνει αν υπάρχει ήδη: ποτέ αντικατάσταση
    except OSError as exc:
        return Result("locked", path, message=f"μετονομασία: {exc}")
    return Result("renamed", path, target, message)
