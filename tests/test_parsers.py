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


def test_non_bill_is_not_recognised(not_a_bill):
    assert parse_bill(extract_text(not_a_bill)) is None


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
