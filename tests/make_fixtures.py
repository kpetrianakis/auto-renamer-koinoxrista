"""Δημιουργεί τα συνθετικά PDF του tests/fixtures.

Μιμούνται τη διάταξη κειμένου των λογαριασμών NRG (μόνο τις γραμμές που
διαβάζουν οι parsers), χωρίς κανένα πραγματικό στοιχείο πελάτη.

    python tests/make_fixtures.py [φάκελος]
"""
import sys
from html import escape
from pathlib import Path

import pymupdf

DISCLAIMER = "ΣΥΝΘΕΤΙΚΟΣ ΛΟΓΑΡΙΑΣΜΟΣ ΓΙΑ TESTS - ΟΧΙ ΠΡΑΓΜΑΤΙΚΑ ΣΤΟΙΧΕΙΑ"


def gas(title, issue, period, kwh, total, due):
    return [[
        "nrg adapt GAS", title, DISCLAIMER,
        "Αριθμός Παροχής", "00000000000000",
        "Ημερομηνία Έκδοσης", issue,
        "Περίοδος Κατανάλωσης", period,
        "kWh", kwh,
        "Σύνολο Τρέχοντος Λογαριασμού ", f"{total}€",
        "Λήξη Προθεσμίας Πληρωμής", due,
    ]]


def power(issue, total, due, charges):
    page1 = [
        "nrg", "Λογαριασμός Χαμηλής Τάσης-Ηλεκτρικής Ενέργειας", "ΕΚΚΑΘΑΡΙΣΤΙΚΟΣ", DISCLAIMER,
        "Αριθμός Παροχής", "0 00000000-00 0",
        "Ημερομηνία Έκδοσης", issue,
        "ΣΥΝΟΛΟ ΛΟΓΑΡΙΑΣΜΟΥ:", f"{total}€",
        "Λήξη Προθεσμίας Πληρωμής", due,
    ]
    page2 = ["ΑΝΑΛΥΣΗ ΧΡΕΩΣΕΩΝ"]
    for kwh, price, month, value in charges:
        page2 += [f"Χρέωση Ημερήσιας Ενέργειας: {kwh}kWhX{price}€/kWh_{month}", f"{value}€"]
    return [page1, page2]


FIXTURES = {
    "gas_settlement_zero.pdf": gas(
        "Εκκαθαριστικός Λογαριασμός Φυσικού Αερίου", "15/09/2026", "01/08/2026 - 31/08/2026",
        "0,00", "17,34", "05/10/2026"),
    "gas_settlement_big.pdf": gas(
        "Εκκαθαριστικός Λογαριασμός Φυσικού Αερίου", "26/05/2026", "20/02/2026 - 21/04/2026",
        "10.954,82", "562,60", "15/06/2026"),
    "gas_estimate.pdf": gas(
        "Έναντι Λογαριασμός Φυσικού Αερίου", "29/04/2026", "20/02/2026 - 11/03/2026",
        "4.612,87", "349,79", "19/05/2026"),
    "power_2026_10.pdf": power("09/10/2026", "82,12", "29/10/2026", [
        (52, "0,28900", "Σεπ'26", "15,03"), (14, "0,29900", "Οκτ'26", "4,19")]),
    "power_2026_03.pdf": power("13/03/2026", "95,15", "02/04/2026", [
        (79, "0,26000", "Φεβ.'26", "20,54"), (36, "0,25232", "Μαρ.'26", "9,08")]),
}


def write_pdf(path: Path, pages: list[list[str]]) -> None:
    with pymupdf.open() as doc:
        for lines in pages:
            # insert_htmlbox: ενσωματωμένες γραμματοσειρές Noto με ελληνικά
            html = "".join(f'<p style="margin:0">{escape(line)}</p>' for line in lines)
            doc.new_page().insert_htmlbox(pymupdf.Rect(50, 50, 545, 800), html, css="* {font-size: 10pt}")
        doc.subset_fonts()
        doc.set_metadata({})
        doc.save(path, garbage=4, deflate=True)


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, pages in FIXTURES.items():
        write_pdf(out / name, pages)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "fixtures")
