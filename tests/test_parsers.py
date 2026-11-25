from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from renamer.model import Bill
from renamer.naming import bill_filename
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
        ("dei_gas_2026_11.pdf", Bill("DEI", "gas", date(2026, 11, 4), 1235, Decimal("245.00"))),
    ],
)
def test_parses_real_bills(fixtures_dir, fixture, expected):
    assert parse_bill(extract_text(fixtures_dir / fixture)) == expected


def test_non_bill_is_not_recognised(not_a_bill):
    assert parse_bill(extract_text(not_a_bill)) is None


def test_unknown_provider_is_not_recognised():
    assert parse_bill("Protergia\nΛογαριασμός Φυσικού Αερίου\n20/11/2026\n") is None


def test_dei_power_bill_is_not_recognised_yet():
    # Μόνο το αέριο της ΔΕΗ υποστηρίζεται· ρεύμα ΔΕΗ μένει ανέγγιχτο ως να έρθει δείγμα
    assert parse_bill("www.dei.gr\nΛΟΓΑΡΙΑΣΜΟΣ ΡΕΥΜΑΤΟΣ\nΗμ/νία Έκδοσης\n04/11/2026\n") is None


def test_dei_gas_missing_field_is_left_empty():
    text = "www.dei.gr\nΛΟΓΑΡΙΑΣΜΟΣ ΦΥΣΙΚΟΥ ΑΕΡΙΟΥ\nΚατανάλωση Φυσικού Αερίου\n0,00 kWh\nΗμ/νία Έκδοσης\n04/11/2026\n"
    bill = parse_bill(text)
    assert bill == Bill("DEI", "gas", date(2026, 11, 4), 0, None)
    assert bill.missing() == ["σύνολο λογαριασμού"]


def test_dei_gas_with_no_fields_raises():
    with pytest.raises(ParseError, match="κανένα"):
        parse_bill("www.dei.gr\nΛΟΓΑΡΙΑΣΜΟΣ ΦΥΣΙΚΟΥ ΑΕΡΙΟΥ\n")


def test_dei_gas_negative_total():
    # π.χ. επιστροφή εγγύησης στον τελικό λογαριασμό
    text = "www.dei.gr\nΛΟΓΑΡΙΑΣΜΟΣ ΦΥΣΙΚΟΥ ΑΕΡΙΟΥ\nΣύνολο Τρέχοντος Λογαριασμού\n-55,00\n"
    assert parse_bill(text).amount == Decimal("-55.00")


def test_missing_field_is_left_empty():
    bill = parse_bill("nrg adapt GAS\nΈναντι Λογαριασμός Φυσικού Αερίου\n20/11/2026\nkWh\n0,00\n")
    assert bill == Bill("NRG", "gas", date(2026, 11, 20), 0, None)
    assert bill.missing() == ["σύνολο λογαριασμού"]


def test_only_amount_found():
    bill = parse_bill("nrg\nΛογαριασμός Χαμηλής Τάσης-Ηλεκτρικής Ενέργειας\nΣΥΝΟΛΟ ΛΟΓΑΡΙΑΣΜΟΥ: 5,00€\n")
    assert bill == Bill("NRG", "revma", None, None, Decimal("5.00"))


def test_recognised_bill_with_no_fields_raises():
    with pytest.raises(ParseError, match="κανένα"):
        parse_bill("nrg adapt GAS\nΈναντι Λογαριασμός Φυσικού Αερίου\n")


def test_negative_gas_total_without_euro_sign():
    # «Τελικός Εκκαθαριστικός»: επιστροφή εγγύησης, το σύνολο γράφεται χωρίς €
    text = (
        "nrg adapt GAS\nΤελικός Εκκαθαριστικός Λογαριασμός Φυσικού Αερίου\n23/11/2026\n0,00€\n"
        "kWh\n34,70\nΕγγύηση \n-250,00€\nΣύνολο Τρέχοντος Λογαριασμού \n-208,37\n"
        "Προηγούμενο Υπόλοιπο\n 0,00€\n"
    )
    assert parse_bill(text) == Bill("NRG", "gas", date(2026, 11, 23), 35, Decimal("-208.37"))


def test_negative_total():
    text = "nrg\nΛογαριασμός Χαμηλής Τάσης-Ηλεκτρικής Ενέργειας\n09/10/2026\n" \
           "Χρέωση Ημερήσιας Ενέργειας: 10kWhX0,28900€/kWh\nΣΥΝΟΛΟ ΛΟΓΑΡΙΑΣΜΟΥ:\n-12,34€\n"
    assert parse_bill(text).amount == Decimal("-12.34")


def test_gr_number():
    assert gr_number("10.954,82") == Decimal("10954.82")
    assert gr_number("-1,03") == Decimal("-1.03")


PRIVATE = Path(__file__).parent / "fixtures" / "private"


@pytest.mark.parametrize("pdf", sorted(PRIVATE.glob("*.pdf")), ids=lambda p: p.name)
def test_private_real_bills(pdf):
    """Πραγματικοί λογαριασμοί, μόνο τοπικά (gitignored), με το σωστό όνομα ως αναμενόμενη τιμή."""
    assert bill_filename(parse_bill(extract_text(pdf))) == pdf.name
