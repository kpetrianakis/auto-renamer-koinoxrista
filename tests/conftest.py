from pathlib import Path

import pymupdf
import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def not_a_bill(tmp_path) -> Path:
    """PDF της nrg που δεν είναι λογαριασμός (π.χ. έντυπο σύμβασης)."""
    path = tmp_path / "source" / "not_a_bill.pdf"
    path.parent.mkdir()
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), "nrg - AITHSH SYMVASHS PROMHTHEIAS 01/10/2026")
        doc.save(path)
    return path
