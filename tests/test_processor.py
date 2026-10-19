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


def test_non_bill_left_untouched(not_a_bill, power_dir):
    src = shutil.copy(not_a_bill, power_dir / "contract.pdf")
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


def test_name_that_would_not_be_recognised_is_refused(fixtures_dir, power_dir, monkeypatch):
    # π.χ. αρνητικά kWh: το όνομα δεν θα αναγνωριζόταν ως επεξεργασμένο -> ατέρμονες μετονομασίες
    from datetime import date
    from decimal import Decimal

    import renamer.processor as processor_mod
    from renamer.model import Bill

    monkeypatch.setattr(
        processor_mod, "parse_bill", lambda text: Bill("NRG", "gas", date(2026, 9, 15), -120, Decimal("1"))
    )
    src = put(fixtures_dir, "gas_settlement_zero.pdf", power_dir, "x.pdf")
    result = process_file(src)
    assert result.status == "error"
    assert [p.name for p in power_dir.iterdir()] == ["x.pdf"]
