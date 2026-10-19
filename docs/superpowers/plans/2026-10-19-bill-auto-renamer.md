# Bill Auto-Renamer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A background watcher that renames NRG gas/power bill PDFs in the shared OneDrive folders to `NRG gas 2026.10.16 0kwh euro 16.78.pdf`, using data read from the PDF.

**Architecture:** Small Python package `renamer`. Pure layers (text extraction → provider parser → filename) are wrapped by `processor` (one file, safe rename), `scanner` (folder scan + memory of final failures + logging) and `watcher` (watchdog events + periodic rescan). A Task Scheduler "at logon" task starts it with the venv's `pythonw.exe`.

**Tech Stack:** Python 3.12 (Microsoft Store), PyMuPDF 1.28.2, watchdog 6.0.0, pytest 8.3.4, PowerShell `ScheduledTasks` module.

**Spec:** `docs/superpowers/specs/2026-10-19-bill-auto-renamer-design.md`

## Global Constraints

- Watched folders: `C:\Users\me\OneDrive\Κοινόχρηστα\Λογαριασμοι Αεριου` and `...\Λογαριασμοι Ρευματος`, non-recursive, `.pdf` only (case-insensitive).
- Filename: `<NRG|DEI> <gas|revma> <YYYY.MM.DD issue date> <int kWh>kwh euro <amount, 2 decimals, dot>.pdf`.
- Processed-name regex: `^(NRG|DEI) (gas|revma) \d{4}\.\d{2}\.\d{2} \d+kwh euro -?\d+\.\d{2}( \(\d+\))?\.pdf$`.
- Amount = current-bill total (gas: «Σύνολο Τρέχοντος Λογαριασμού», power: «ΣΥΝΟΛΟ ΛΟΓΑΡΙΑΣΜΟΥ:»), never «ΣΥΝΟΛΙΚΟ ΠΟΣΟ ΠΛΗΡΩΜΗΣ».
- Never overwrite: collisions get ` (2)`, ` (3)`, …
- Unrecognized PDFs and parse failures are left untouched and logged once per file version (mtime).
- Log: `<root>\auto-renamer.log`, rotating 1 MB × 3, UTF-8. `--dry-run` writes no log file.
- Bill in the wrong folder: rename in place by content + warning, never move.
- Rescan every 600 s; a file counts as settled when its mtime is ≥ 5 s old.
- Commands run from the repo root in Git Bash: `.venv/Scripts/python -m pytest …`.

## Review Focus

1. A PDF still being written / synced when the event fires — must not be renamed half-read and must be retried once it settles (Task 5 settle test, Task 6 watcher test).
2. Browser duplicates (`… (1).pdf`) that map to the same target name — second one gets ` (2)`, nothing overwritten (Task 4 collision test).
3. Non-bill PDFs (contract forms) in the folder — untouched, logged once, not re-parsed every rescan (Task 5 "final once" test).
4. A credit bill with a negative total (`-12,34€`) — renamed `… euro -12.34.pdf` and still recognised as processed (Task 2 + Task 3 tests).
5. The watcher's own rename firing a new event — must be ignored, no loop (Task 4 skip test, Task 6 watcher test).

---

### Task 1: Project scaffolding, fixtures, model, PDF text

**Files:**
- Create: `.gitignore`, `requirements.txt`, `renamer/__init__.py`, `renamer/config.py`, `renamer/model.py`, `renamer/pdftext.py`
- Create: `tests/__init__.py`, `tests/conftest.py`, `tests/test_pdftext.py`, `tests/fixtures/*.pdf`

**Interfaces:**
- Produces: `renamer.model.Bill(provider: str, kind: str, issue_date: date, kwh: int, amount: Decimal)` (frozen dataclass); `renamer.pdftext.extract_text(path: Path) -> str`; `renamer.config` constants `DEFAULT_ROOT`, `FOLDER_KINDS: dict[str, str]`, `LOG_NAME`, `RESCAN_SECONDS`, `SETTLE_SECONDS`; pytest fixture `fixtures_dir -> Path`.

- [ ] **Step 1: git init, ignore file, requirements, venv**

```bash
git init
cat > .gitignore <<'EOF'
.venv/
__pycache__/
.pytest_cache/
EOF
cat > requirements.txt <<'EOF'
pymupdf==1.28.2
watchdog==6.0.0
pytest==8.3.4
EOF
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```
Expected: installs succeed.

- [ ] **Step 2: Copy sample PDFs into fixtures (stable names)**

```bash
SRC="/c/Users/me/OneDrive/Κοινόχρηστα"
mkdir -p tests/fixtures
cp "$SRC/Λογαριασμοι Αεριου/nrg gas 15.9.2026 0kwh euro 17.34.pdf"   tests/fixtures/gas_settlement_zero.pdf
cp "$SRC/Λογαριασμοι Αεριου/nrg gas 26.5.2026 euro 562.60.pdf"      tests/fixtures/gas_settlement_big.pdf
cp "$SRC/Λογαριασμοι Αεριου/nrg gas 29.4.2026 euro 349.79.pdf"      tests/fixtures/gas_estimate.pdf
cp "$SRC/Λογαριασμοι Ρευματος/nrg revma 9.10.2026 66kwh euro 82.12.pdf" tests/fixtures/power_2026_10.pdf
cp "$SRC/Λογαριασμοι Ρευματος/2026 03 - NRG Revma - Εκκαθαριστικος.pdf" tests/fixtures/power_2026_03.pdf
cp "$SRC/Λογαριασμοι Ρευματος/contract-form.pdf"               tests/fixtures/not_a_bill.pdf
ls tests/fixtures
```
Expected: 6 files listed.

- [ ] **Step 3: Write config, model, conftest**

`renamer/__init__.py`: empty file.

`renamer/config.py`:
```python
from pathlib import Path

DEFAULT_ROOT = Path(r"C:\Users\me\OneDrive\Κοινόχρηστα")

# Φάκελος -> τύπος λογαριασμού που περιμένουμε να περιέχει
FOLDER_KINDS = {
    "Λογαριασμοι Αεριου": "gas",
    "Λογαριασμοι Ρευματος": "revma",
}

LOG_NAME = "auto-renamer.log"
RESCAN_SECONDS = 600
SETTLE_SECONDS = 5.0
```

`renamer/model.py`:
```python
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
```

`tests/__init__.py`: empty file.

`tests/conftest.py`:
```python
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
```

- [ ] **Step 4: Write the failing test**

`tests/test_pdftext.py`:
```python
from renamer.pdftext import extract_text


def test_extracts_text_from_all_pages(fixtures_dir):
    text = extract_text(fixtures_dir / "power_2026_10.pdf")
    assert "Λογαριασμός Χαμηλής Τάσης-Ηλεκτρικής Ενέργειας" in text  # σελίδα 1
    assert "Χρέωση Ημερήσιας Ενέργειας: 52kWhX" in text  # σελίδα 2
```

- [ ] **Step 5: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_pdftext.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'renamer.pdftext'`

- [ ] **Step 6: Implement**

`renamer/pdftext.py`:
```python
from pathlib import Path

import pymupdf


def extract_text(path: Path) -> str:
    with pymupdf.open(path) as doc:
        return "\n".join(page.get_text() for page in doc)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_pdftext.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add .gitignore requirements.txt renamer tests docs
git commit -m "chore: scaffold renamer package with PDF text extraction

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Filename building and collision handling

**Files:**
- Create: `renamer/naming.py`
- Test: `tests/test_naming.py`

**Interfaces:**
- Consumes: `Bill` (Task 1).
- Produces: `bill_filename(bill: Bill) -> str`; `is_processed(name: str) -> bool`; `unique_path(directory: Path, filename: str) -> Path`.

- [ ] **Step 1: Write the failing tests**

`tests/test_naming.py`:
```python
from datetime import date
from decimal import Decimal

from renamer.model import Bill
from renamer.naming import bill_filename, is_processed, unique_path


def bill(**overrides):
    values = dict(provider="NRG", kind="gas", issue_date=date(2026, 9, 5), kwh=0, amount=Decimal("17.3"))
    values.update(overrides)
    return Bill(**values)


def test_filename_pads_date_and_formats_amount():
    assert bill_filename(bill()) == "NRG gas 2026.09.05 0kwh euro 17.30.pdf"


def test_filename_for_power_and_dei():
    assert bill_filename(bill(provider="DEI", kind="revma", kwh=66, amount=Decimal("82.12"))) == (
        "DEI revma 2026.09.05 66kwh euro 82.12.pdf"
    )


def test_filename_negative_amount_is_still_processed():
    name = bill_filename(bill(amount=Decimal("-12.34")))
    assert name == "NRG gas 2026.09.05 0kwh euro -12.34.pdf"
    assert is_processed(name)


def test_is_processed():
    assert is_processed("NRG gas 2026.10.16 0kwh euro 16.78.pdf")
    assert is_processed("NRG revma 2026.10.09 66kwh euro 82.12 (2).pdf")
    assert not is_processed("nrg gas 15.9.2026 0kwh euro 17.34.pdf")  # παλιό format
    assert not is_processed("invoice (12).pdf")
    assert not is_processed("NRG gas 2026.10.16 0kwh euro 16.78.pdf.crdownload")


def test_unique_path_free_name(tmp_path):
    assert unique_path(tmp_path, "a b.pdf") == tmp_path / "a b.pdf"


def test_unique_path_adds_counter(tmp_path):
    (tmp_path / "a b.pdf").touch()
    (tmp_path / "a b (2).pdf").touch()
    assert unique_path(tmp_path, "a b.pdf") == tmp_path / "a b (3).pdf"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_naming.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'renamer.naming'`

- [ ] **Step 3: Implement**

`renamer/naming.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_naming.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add renamer/naming.py tests/test_naming.py
git commit -m "feat: build bill filenames and avoid collisions

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: NRG parser and parser registry

**Files:**
- Create: `renamer/parsers/__init__.py`, `renamer/parsers/common.py`, `renamer/parsers/nrg.py`
- Test: `tests/test_parsers.py`

**Interfaces:**
- Consumes: `Bill` (Task 1), `extract_text` (Task 1, tests only).
- Produces: `renamer.parsers.parse_bill(text: str) -> Bill | None` (None = not a known bill); `renamer.parsers.ParseError` (bill recognised, field missing). Each provider module exposes `matches(text: str) -> bool` and `parse(text: str) -> Bill`.

Facts verified on the real samples (do not change without re-checking):
- Issue date = the first line that is exactly `DD/MM/YYYY`.
- Gas title contains «Λογαριασμός Φυσικού Αερίου» (both «Εκκαθαριστικός» and «Έναντι»). Gas kWh = number on the line after a line that is exactly `kWh`.
- Power title «Λογαριασμός Χαμηλής Τάσης-Ηλεκτρικής Ενέργειας». Power kWh = sum of all `Χρέωση … Ενέργειας: <N>kWhX` lines (e.g. 52 + 14 = 66).
- Numbers are Greek format: `10.954,82`.

- [ ] **Step 1: Write the failing tests**

`tests/test_parsers.py`:
```python
from datetime import date
from decimal import Decimal

import pytest

from renamer.model import Bill
from renamer.parsers import ParseError, parse_bill
from renamer.parsers.common import gr_number
from renamer.pdftext import extract_text


@pytest.mark.parametrize(
    "fixture, expected",
    [
        ("gas_settlement_zero.pdf", Bill("NRG", "gas", date(2026, 9, 15), 0, Decimal("17.34"))),
        ("gas_settlement_big.pdf", Bill("NRG", "gas", date(2026, 5, 26), 10955, Decimal("562.60"))),
        ("gas_estimate.pdf", Bill("NRG", "gas", date(2026, 4, 29), 4613, Decimal("349.79"))),
        ("power_2026_10.pdf", Bill("NRG", "revma", date(2026, 10, 9), 66, Decimal("82.12"))),
        ("power_2026_03.pdf", Bill("NRG", "revma", date(2026, 3, 13), 115, Decimal("95.15"))),
    ],
)
def test_parses_real_bills(fixtures_dir, fixture, expected):
    assert parse_bill(extract_text(fixtures_dir / fixture)) == expected


def test_non_bill_is_not_recognised(fixtures_dir):
    assert parse_bill(extract_text(fixtures_dir / "not_a_bill.pdf")) is None


def test_unknown_provider_is_not_recognised():
    assert parse_bill("ΔΕΗ\nΛογαριασμός Φυσικού Αερίου\n20/11/2026\n") is None


def test_recognised_bill_with_missing_field_raises():
    with pytest.raises(ParseError, match="σύνολο"):
        parse_bill("nrg adapt GAS\nΈναντι Λογαριασμός Φυσικού Αερίου\n20/11/2026\nkWh\n0,00\n")


def test_negative_total():
    text = "nrg\nΛογαριασμός Χαμηλής Τάσης-Ηλεκτρικής Ενέργειας\n09/10/2026\n" \
           "Χρέωση Ημερήσιας Ενέργειας: 10kWhX0,28900€/kWh\nΣΥΝΟΛΟ ΛΟΓΑΡΙΑΣΜΟΥ:\n-12,34€\n"
    assert parse_bill(text).amount == Decimal("-12.34")


def test_gr_number():
    assert gr_number("10.954,82") == Decimal("10954.82")
    assert gr_number("-1,03") == Decimal("-1.03")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_parsers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'renamer.parsers'`

- [ ] **Step 3: Implement**

`renamer/parsers/common.py`:
```python
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
```

`renamer/parsers/nrg.py`:
```python
import re
from decimal import Decimal

from ..model import Bill
from .common import NUMBER, ParseError, find, gr_date, gr_number, round_kwh

GAS_TITLE = "Λογαριασμός Φυσικού Αερίου"  # «Εκκαθαριστικός» και «Έναντι»
POWER_TITLE = "Λογαριασμός Χαμηλής Τάσης-Ηλεκτρικής Ενέργειας"
ISSUE_DATE = r"^(\d{2}/\d{2}/\d{4})$"  # η πρώτη «σκέτη» ημερομηνία είναι η έκδοση


def matches(text: str) -> bool:
    return "nrg" in text.lower() and (GAS_TITLE in text or POWER_TITLE in text)


def parse(text: str) -> Bill:
    issue_date = gr_date(find(ISSUE_DATE, text, "ημερομηνία έκδοσης"))
    if GAS_TITLE in text:
        kind = "gas"
        kwh = gr_number(find(rf"^kWh\n({NUMBER})$", text, "kWh"))
        amount = find(rf"Σύνολο Τρέχοντος Λογαριασμού\s*({NUMBER})€", text, "σύνολο λογαριασμού")
    else:
        kind = "revma"
        charges = re.findall(r"Χρέωση [^:\n]*Ενέργειας: (\d+)kWhX", text)
        if not charges:
            raise ParseError("δεν βρέθηκε: kWh")
        kwh = sum(Decimal(c) for c in charges)
        amount = find(rf"ΣΥΝΟΛΟ ΛΟΓΑΡΙΑΣΜΟΥ:\s*({NUMBER})€", text, "σύνολο λογαριασμού")
    return Bill("NRG", kind, issue_date, round_kwh(kwh), gr_number(amount))
```

`renamer/parsers/__init__.py`:
```python
from ..model import Bill
from . import nrg
from .common import ParseError

# Νέος πάροχος (π.χ. dei): module με matches()/parse() και προσθήκη εδώ.
PARSERS = [nrg]

__all__ = ["ParseError", "parse_bill"]


def parse_bill(text: str) -> Bill | None:
    for parser in PARSERS:
        if parser.matches(text):
            return parser.parse(text)
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_parsers.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add renamer/parsers tests/test_parsers.py
git commit -m "feat: parse NRG gas and power bills

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Process a single file

**Files:**
- Create: `renamer/processor.py`
- Test: `tests/test_processor.py`

**Interfaces:**
- Consumes: `extract_text`, `parse_bill`, `ParseError`, `bill_filename`, `is_processed`, `unique_path`, `config.FOLDER_KINDS`.
- Produces: `Result(status: str, source: Path, target: Path | None = None, message: str = "")` frozen dataclass, status ∈ `"renamed" | "would_rename" | "skipped" | "unrecognized" | "error" | "locked"`; `process_file(path: Path, *, dry_run: bool = False) -> Result`. `"locked"` means "retry later" (unreadable or rename refused); `"unrecognized"` and `"error"` are final for that file version.

- [ ] **Step 1: Write the failing tests**

`tests/test_processor.py`:
```python
import shutil

import pytest

from renamer.processor import process_file


@pytest.fixture
def power_dir(tmp_path):
    d = tmp_path / "Λογαριασμοι Ρευματος"
    d.mkdir()
    return d


def put(fixtures_dir, name, folder, as_name):
    return shutil.copy(fixtures_dir / name, folder / as_name)


def test_renames_bill(fixtures_dir, power_dir):
    src = put(fixtures_dir, "power_2026_10.pdf", power_dir, "800Rz.pdf")
    result = process_file(src)
    assert result.status == "renamed"
    assert result.target.name == "NRG revma 2026.10.09 66kwh euro 82.12.pdf"
    assert [p.name for p in power_dir.iterdir()] == [result.target.name]
    assert result.message == ""


def test_dry_run_changes_nothing(fixtures_dir, power_dir):
    src = put(fixtures_dir, "power_2026_10.pdf", power_dir, "x.pdf")
    result = process_file(src, dry_run=True)
    assert result.status == "would_rename"
    assert result.target.name == "NRG revma 2026.10.09 66kwh euro 82.12.pdf"
    assert [p.name for p in power_dir.iterdir()] == ["x.pdf"]


def test_collision_gets_counter(fixtures_dir, power_dir):
    a = put(fixtures_dir, "power_2026_10.pdf", power_dir, "a.pdf")
    b = put(fixtures_dir, "power_2026_10.pdf", power_dir, "a (1).pdf")
    process_file(a)
    result = process_file(b)
    assert result.target.name == "NRG revma 2026.10.09 66kwh euro 82.12 (2).pdf"
    assert len(list(power_dir.iterdir())) == 2


def test_already_processed_and_non_pdf_are_skipped(fixtures_dir, power_dir):
    done = put(fixtures_dir, "power_2026_10.pdf", power_dir, "NRG revma 2026.10.09 66kwh euro 82.12.pdf")
    other = power_dir / "notes.txt"
    other.write_text("x")
    assert process_file(done).status == "skipped"
    assert process_file(other).status == "skipped"


def test_uppercase_extension_is_processed(fixtures_dir, power_dir):
    src = put(fixtures_dir, "power_2026_10.pdf", power_dir, "BILL.PDF")
    assert process_file(src).status == "renamed"


def test_non_bill_left_untouched(fixtures_dir, power_dir):
    src = put(fixtures_dir, "not_a_bill.pdf", power_dir, "800Rz.pdf")
    assert process_file(src).status == "unrecognized"
    assert src.exists()


def test_corrupt_pdf_is_retryable(power_dir):
    src = power_dir / "half.pdf"
    src.write_bytes(b"%PDF-1.7\n")  # μισογραμμένο
    assert process_file(src).status == "locked"
    assert src.exists()


def test_wrong_folder_renamed_with_warning(fixtures_dir, power_dir):
    src = put(fixtures_dir, "gas_settlement_zero.pdf", power_dir, "invoice.pdf")
    result = process_file(src)
    assert result.status == "renamed"
    assert result.target.parent == power_dir
    assert result.target.name == "NRG gas 2026.09.15 0kwh euro 17.34.pdf"
    assert "gas" in result.message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_processor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'renamer.processor'`

- [ ] **Step 3: Implement**

`renamer/processor.py`:
```python
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

    target = unique_path(path.parent, bill_filename(bill))
    if dry_run:
        return Result("would_rename", path, target, message)
    try:
        path.rename(target)  # στα Windows αποτυγχάνει αν υπάρχει ήδη: ποτέ αντικατάσταση
    except OSError as exc:
        return Result("locked", path, message=f"μετονομασία: {exc}")
    return Result("renamed", path, target, message)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_processor.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add renamer/processor.py tests/test_processor.py
git commit -m "feat: process and safely rename a single bill PDF

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Scanner (folder scan, settle check, final-result memory, logging)

**Files:**
- Create: `renamer/scanner.py`
- Test: `tests/test_scanner.py`

**Interfaces:**
- Consumes: `process_file`, `Result`, `is_processed`.
- Produces: `is_settled(path: Path, seconds: float) -> bool`; `Scanner(dirs: list[Path], *, dry_run: bool = False, settle_seconds: float = 5.0)` with `scan_all() -> list[Result]` and `handle(path: Path) -> Result | None` (None = ignored without processing). Logs to logger `"renamer"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_scanner.py`:
```python
import logging
import os
import shutil
import time

import pytest

import renamer.scanner as scanner_mod
from renamer.scanner import Scanner, is_settled


@pytest.fixture
def dirs(tmp_path):
    gas, power = tmp_path / "Λογαριασμοι Αεριου", tmp_path / "Λογαριασμοι Ρευματος"
    gas.mkdir()
    power.mkdir()
    return gas, power


def age(path, seconds=60):
    t = time.time() - seconds
    os.utime(path, (t, t))


def test_scan_all_renames_settled_files_in_both_folders(fixtures_dir, dirs):
    gas, power = dirs
    age(shutil.copy(fixtures_dir / "gas_estimate.pdf", gas / "invoice (12).pdf"))
    age(shutil.copy(fixtures_dir / "power_2026_03.pdf", power / "x.pdf"))
    results = Scanner(list(dirs), settle_seconds=5).scan_all()
    assert sorted(r.status for r in results) == ["renamed", "renamed"]
    assert (gas / "NRG gas 2026.04.29 4613kwh euro 349.79.pdf").exists()
    assert (power / "NRG revma 2026.03.13 115kwh euro 95.15.pdf").exists()


def test_scan_all_waits_for_fresh_files(fixtures_dir, dirs):
    gas, _ = dirs
    shutil.copy(fixtures_dir / "gas_estimate.pdf", gas / "fresh.pdf")  # mtime = τώρα
    assert Scanner(list(dirs), settle_seconds=5).scan_all() == []
    assert (gas / "fresh.pdf").exists()


def test_unrecognized_is_processed_once_per_version(fixtures_dir, dirs, monkeypatch):
    _, power = dirs
    src = shutil.copy(fixtures_dir / "not_a_bill.pdf", power / "800Rz.pdf")
    age(src)
    calls = []
    real = scanner_mod.process_file
    monkeypatch.setattr(scanner_mod, "process_file", lambda p, **kw: calls.append(p) or real(p, **kw))
    s = Scanner(list(dirs), settle_seconds=5)
    s.scan_all()
    s.scan_all()
    assert len(calls) == 1
    age(src, 30)  # το αρχείο άλλαξε -> ξαναεξετάζεται
    s.scan_all()
    assert len(calls) == 2


def test_locked_is_retried_but_logged_once(dirs, caplog):
    _, power = dirs
    src = power / "half.pdf"
    src.write_bytes(b"%PDF-1.7\n")
    age(src)
    s = Scanner(list(dirs), settle_seconds=5)
    with caplog.at_level(logging.INFO, logger="renamer"):
        assert s.scan_all()[0].status == "locked"
        assert s.scan_all()[0].status == "locked"
    assert sum("half.pdf" in r.getMessage() for r in caplog.records) == 1


def test_logs_rename_and_wrong_folder(fixtures_dir, dirs, caplog):
    _, power = dirs
    age(shutil.copy(fixtures_dir / "gas_settlement_zero.pdf", power / "invoice.pdf"))
    with caplog.at_level(logging.INFO, logger="renamer"):
        Scanner(list(dirs), settle_seconds=5).scan_all()
    text = caplog.text
    assert "invoice.pdf → NRG gas 2026.09.15 0kwh euro 17.34.pdf" in text
    assert "Λάθος φάκελος" in text


def test_missing_folder_is_logged_not_fatal(tmp_path, caplog):
    with caplog.at_level(logging.ERROR, logger="renamer"):
        assert Scanner([tmp_path / "nope"]).scan_all() == []
    assert "δεν υπάρχει" in caplog.text


def test_is_settled(tmp_path):
    f = tmp_path / "a.pdf"
    f.touch()
    assert not is_settled(f, 5)
    age(f)
    assert is_settled(f, 5)
    assert not is_settled(tmp_path / "missing.pdf", 5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_scanner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'renamer.scanner'`

- [ ] **Step 3: Implement**

`renamer/scanner.py`:
```python
import logging
import time
from pathlib import Path

from .naming import is_processed
from .processor import Result, process_file

log = logging.getLogger("renamer")

# Οριστικά αποτελέσματα: δεν ξαναεξετάζονται μέχρι να αλλάξει το αρχείο (mtime)
FINAL = {"unrecognized", "error"}


def is_settled(path: Path, seconds: float) -> bool:
    try:
        return time.time() - path.stat().st_mtime >= seconds
    except FileNotFoundError:
        return False


class Scanner:
    def __init__(self, dirs: list[Path], *, dry_run: bool = False, settle_seconds: float = 5.0):
        self.dirs = dirs
        self.dry_run = dry_run
        self.settle_seconds = settle_seconds
        self._final: dict[Path, float] = {}
        self._locked: dict[Path, float] = {}

    def scan_all(self) -> list[Result]:
        results = []
        for directory in self.dirs:
            if not directory.is_dir():
                log.error("Ο φάκελος δεν υπάρχει: %s", directory)
                continue
            for path in sorted(directory.iterdir()):
                if path.is_file() and is_settled(path, self.settle_seconds):
                    result = self.handle(path)
                    if result is not None:
                        results.append(result)
        return results

    def handle(self, path: Path) -> Result | None:
        if path.suffix.lower() != ".pdf" or is_processed(path.name):
            return None
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            return None
        if self._final.get(path) == mtime:
            return None

        result = process_file(path, dry_run=self.dry_run)
        if result.status in FINAL:
            self._final[path] = mtime
        if result.status == "locked":
            if self._locked.get(path) == mtime:
                return result  # ήδη καταγραμμένο· απλώς ξαναδοκιμάζουμε σιωπηλά
            self._locked[path] = mtime
        _log(result)
        return result


def _log(result: Result) -> None:
    name = result.source.name
    if result.status in ("renamed", "would_rename"):
        prefix = "[dry-run] " if result.status == "would_rename" else ""
        log.info("%sΜετονομασία: %s → %s", prefix, name, result.target.name)
        if result.message:
            log.warning("Λάθος φάκελος: %s (%s)", result.target.name, result.message)
    elif result.status == "unrecognized":
        log.info("Μη αναγνωρισμένο PDF, μένει ως έχει: %s", name)
    elif result.status == "error":
        log.warning("Σφάλμα στο %s: %s", name, result.message)
    elif result.status == "locked":
        log.info("Θα ξαναδοκιμαστεί αργότερα: %s (%s)", name, result.message)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_scanner.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add renamer/scanner.py tests/test_scanner.py
git commit -m "feat: scan folders with settle check and once-per-version logging

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Watcher (watchdog events + periodic rescan)

**Files:**
- Create: `renamer/watcher.py`
- Test: `tests/test_watcher.py`

**Interfaces:**
- Consumes: `Scanner` (`.dirs`, `.settle_seconds`, `.scan_all()`, `.handle()`), `is_settled`.
- Produces: `run_watcher(scanner: Scanner, *, rescan_seconds: float, stop: threading.Event | None = None) -> None` — blocks until `stop` is set; does an initial `scan_all()`.

- [ ] **Step 1: Write the failing test**

`tests/test_watcher.py`:
```python
import shutil
import threading
import time

from renamer.scanner import Scanner
from renamer.watcher import run_watcher

TARGET = "NRG revma 2026.10.09 66kwh euro 82.12.pdf"


def wait_for(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.2)
    return False


def test_new_file_is_renamed_while_watching(fixtures_dir, tmp_path):
    power = tmp_path / "Λογαριασμοι Ρευματος"
    power.mkdir()
    scanner = Scanner([power], settle_seconds=0.5)
    stop = threading.Event()
    thread = threading.Thread(target=run_watcher, args=(scanner,), kwargs=dict(rescan_seconds=600, stop=stop))
    thread.start()
    try:
        time.sleep(1)  # ο observer ξεκινά
        shutil.copy(fixtures_dir / "power_2026_10.pdf", power / "download.pdf")
        assert wait_for(lambda: (power / TARGET).exists())
        time.sleep(2)  # το δικό μας rename δεν πρέπει να προκαλέσει νέα μετονομασία
        assert [p.name for p in power.iterdir()] == [TARGET]
    finally:
        stop.set()
        thread.join(timeout=10)
    assert not thread.is_alive()


def test_initial_scan_picks_up_existing_files(fixtures_dir, tmp_path):
    power = tmp_path / "Λογαριασμοι Ρευματος"
    power.mkdir()
    shutil.copy2(fixtures_dir / "power_2026_10.pdf", power / "old.pdf")  # copy2: παλιό mtime
    stop = threading.Event()
    thread = threading.Thread(
        target=run_watcher, args=(Scanner([power], settle_seconds=0.5),), kwargs=dict(rescan_seconds=600, stop=stop)
    )
    thread.start()
    try:
        assert wait_for(lambda: (power / TARGET).exists())
    finally:
        stop.set()
        thread.join(timeout=10)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_watcher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'renamer.watcher'`

- [ ] **Step 3: Implement**

`renamer/watcher.py`:
```python
import logging
import queue
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .scanner import Scanner, is_settled

log = logging.getLogger("renamer")


class _Handler(FileSystemEventHandler):
    def __init__(self, events: queue.Queue):
        self.events = events

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self.events.put(Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        self.on_created(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        # π.χ. ο browser μετονομάζει .crdownload -> .pdf
        if not event.is_directory:
            self.events.put(Path(event.dest_path))


def run_watcher(scanner: Scanner, *, rescan_seconds: float, stop: threading.Event | None = None) -> None:
    stop = stop or threading.Event()
    events: queue.Queue[Path] = queue.Queue()
    observer = Observer()
    for directory in scanner.dirs:
        observer.schedule(_Handler(events), str(directory), recursive=False)
    observer.start()
    try:
        scanner.scan_all()
        pending: set[Path] = set()
        next_rescan = time.monotonic() + rescan_seconds
        while not stop.is_set():
            try:
                pending.add(events.get(timeout=1))
            except queue.Empty:
                pass
            for path in list(pending):
                if not path.exists():
                    pending.discard(path)
                elif is_settled(path, scanner.settle_seconds):
                    pending.discard(path)
                    _safe(scanner.handle, path)
            if time.monotonic() >= next_rescan:
                _safe(scanner.scan_all)
                next_rescan = time.monotonic() + rescan_seconds
    finally:
        observer.stop()
        observer.join()


def _safe(func, *args) -> None:
    """Ένα απρόσμενο σφάλμα σε ένα αρχείο δεν πρέπει να σταματήσει τον watcher."""
    try:
        func(*args)
    except Exception:
        log.exception("Απρόσμενο σφάλμα")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_watcher.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add renamer/watcher.py tests/test_watcher.py
git commit -m "feat: watch folders with watchdog and periodic rescan

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: CLI entry point and logging setup

**Files:**
- Create: `renamer/__main__.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `config`, `Scanner`, `run_watcher`.
- Produces: `main(argv: list[str] | None = None) -> int`. CLI: `python -m renamer` (watch), `--once`, `--dry-run` (implies `--once`, no log file), `--root PATH`.

- [ ] **Step 1: Write the failing tests**

`tests/test_main.py`:
```python
import os
import shutil
import time

from renamer.__main__ import main


def make_root(tmp_path, fixtures_dir):
    power = tmp_path / "Λογαριασμοι Ρευματος"
    power.mkdir()
    (tmp_path / "Λογαριασμοι Αεριου").mkdir()
    src = shutil.copy(fixtures_dir / "power_2026_10.pdf", power / "x.pdf")
    old = time.time() - 60
    os.utime(src, (old, old))
    return power


def test_dry_run_prints_plan_and_changes_nothing(tmp_path, fixtures_dir, capsys):
    power = make_root(tmp_path, fixtures_dir)
    assert main(["--dry-run", "--root", str(tmp_path)]) == 0
    assert "x.pdf → NRG revma 2026.10.09 66kwh euro 82.12.pdf" in capsys.readouterr().err
    assert [p.name for p in power.iterdir()] == ["x.pdf"]
    assert not (tmp_path / "auto-renamer.log").exists()


def test_once_renames_and_writes_log(tmp_path, fixtures_dir):
    power = make_root(tmp_path, fixtures_dir)
    assert main(["--once", "--root", str(tmp_path)]) == 0
    assert [p.name for p in power.iterdir()] == ["NRG revma 2026.10.09 66kwh euro 82.12.pdf"]
    log_text = (tmp_path / "auto-renamer.log").read_text(encoding="utf-8")
    assert "x.pdf → NRG revma" in log_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'renamer.__main__'`

- [ ] **Step 3: Implement**

`renamer/__main__.py`:
```python
import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import config
from .scanner import Scanner
from .watcher import run_watcher

log = logging.getLogger("renamer")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="renamer", description="Μετονομασία λογαριασμών ρεύματος/αερίου")
    parser.add_argument("--once", action="store_true", help="μία σάρωση και έξοδος")
    parser.add_argument("--dry-run", action="store_true", help="μόνο εμφάνιση, χωρίς αλλαγές (υπονοεί --once)")
    parser.add_argument("--root", type=Path, default=config.DEFAULT_ROOT)
    args = parser.parse_args(argv)

    _setup_logging(None if args.dry_run else args.root / config.LOG_NAME)
    scanner = Scanner(
        [args.root / name for name in config.FOLDER_KINDS],
        dry_run=args.dry_run,
        settle_seconds=config.SETTLE_SECONDS,
    )
    if args.once or args.dry_run:
        scanner.scan_all()
        return 0

    log.info("Εκκίνηση watcher: %s", args.root)
    try:
        run_watcher(scanner, rescan_seconds=config.RESCAN_SECONDS)
    except KeyboardInterrupt:
        pass
    except Exception:
        log.exception("Ο watcher σταμάτησε απρόσμενα")
        return 1  # μη μηδενικός κωδικός -> ο Task Scheduler τον ξαναξεκινά
    log.info("Τερματισμός watcher")
    return 0


def _setup_logging(log_file: Path | None) -> None:
    handlers: list[logging.Handler] = []
    if log_file is not None:
        handlers.append(RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"))
    if sys.stderr is not None:  # το pythonw.exe δεν έχει κονσόλα
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # κονσόλα cp1252
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers, force=True
    )


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass, then the full suite**

Run: `.venv/Scripts/python -m pytest tests/test_main.py -v` → Expected: 2 passed
Run: `.venv/Scripts/python -m pytest -q` → Expected: all passed (36)

- [ ] **Step 5: Commit**

```bash
git add renamer/__main__.py tests/test_main.py
git commit -m "feat: add CLI with dry-run, once and watch modes

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Migrate existing files, install the scheduled task, live check

**Files:**
- Create: `install_task.ps1`

**Interfaces:**
- Consumes: `python -m renamer` CLI (Task 7).

- [ ] **Step 1: Dry-run on the real folder**

Run: `.venv/Scripts/python -m renamer --dry-run`
Expected: one `[dry-run] Μετονομασία: … → …` line per bill, `Μη αναγνωρισμένο PDF … contract-form.pdf`, nothing changed on disk. Known differences to point out to the user: `nrg revma 13.6.2026 …` → `2026.07.13`, `nrg gas 24.7.2026 …` → `2026.07.23` (issue date printed in the PDF).

- [ ] **Step 2: STOP — show the full list to the user and wait for explicit approval.**

- [ ] **Step 3: Apply**

Run: `.venv/Scripts/python -m renamer --once`
Then: `ls "/c/Users/me/OneDrive/Κοινόχρηστα/Λογαριασμοι Αεριου" "/c/Users/me/OneDrive/Κοινόχρηστα/Λογαριασμοι Ρευματος"`
Expected: all bills in the new format; `contract-form.pdf` and `desktop.ini` untouched; `auto-renamer.log` exists in the root.

- [ ] **Step 4: Write the install script**

`install_task.ps1`:
```powershell
# Καταχωρεί τον watcher στον Task Scheduler: ξεκινά στο login, ξανασηκώνεται αν πέσει.
$ErrorActionPreference = 'Stop'
$taskName = 'Koinoxrista Auto-Renamer'
$pythonw = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $pythonw)) { throw "Δεν βρέθηκε το $pythonw — φτιάξε πρώτα το .venv" }

$action = New-ScheduledTaskAction -Execute $pythonw -Argument '-m renamer' -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State
```

- [ ] **Step 5: Install and verify it runs**

Run (PowerShell): `.\install_task.ps1`
Expected: `State: Running`. Then check the last lines of `auto-renamer.log` contain `Εκκίνηση watcher`.

- [ ] **Step 6: Live check**

Copy a fixture into the real power folder under a throwaway name (`tests/fixtures/power_2026_10.pdf` → `…\Λογαριασμοι Ρευματος\live-test.pdf`). Within ~10 s it must become `NRG revma 2026.10.09 66kwh euro 82.12 (2).pdf` (collision with the real one). Then delete that `(2)` copy and confirm the log shows the rename.

- [ ] **Step 7: Commit**

```bash
git add install_task.ps1
git commit -m "feat: add Task Scheduler install script

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

To remove later: `Unregister-ScheduledTask -TaskName 'Koinoxrista Auto-Renamer' -Confirm:$false`.
