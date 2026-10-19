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
