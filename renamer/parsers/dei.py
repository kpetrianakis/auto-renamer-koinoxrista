"""ΔΕΗ: μόνο λογαριασμοί φυσικού αερίου (myBuilding GasControl).

Σε αντίθεση με τη NRG, κάθε τιμή βρίσκεται στη γραμμή κάτω από την ετικέτα της,
και η πρώτη σκέτη ημερομηνία είναι η «Επόμενη καταμέτρηση», όχι η έκδοση.
Γι' αυτό κάθε pattern αγκυρώνεται στην ετικέτα.
"""
from ..model import Bill
from .common import NUMBER, find, gr_number, make_bill

GAS_TITLE = "ΛΟΓΑΡΙΑΣΜΟΣ ΦΥΣΙΚΟΥ ΑΕΡΙΟΥ"
ISSUE_DATE = r"^Ημ/νία Έκδοσης\s*(\d{2}/\d{2}/\d{4})$"
KWH = rf"^Κατανάλωση Φυσικού Αερίου\s*({NUMBER})\s*kWh$"
# Το σύνολο του τρέχοντος λογαριασμού (χωρίς προηγούμενο ανεξόφλητο), όπως στη NRG
TOTAL = rf"^Σύνολο Τρέχοντος Λογαριασμού\s*({NUMBER})\s*€?$"


def matches(text: str) -> bool:
    return "dei.gr" in text.lower() and GAS_TITLE in text


def parse(text: str) -> Bill:
    kwh = find(KWH, text)
    return make_bill(
        "DEI",
        "gas",
        find(ISSUE_DATE, text),
        gr_number(kwh) if kwh is not None else None,
        find(TOTAL, text),
    )
