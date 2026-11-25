import re
from decimal import Decimal

from ..model import Bill
from .common import NUMBER, find, gr_number, make_bill

GAS_TITLE = "Λογαριασμός Φυσικού Αερίου"  # «Εκκαθαριστικός», «Τελικός Εκκαθαριστικός» και «Έναντι»
POWER_TITLE = "Λογαριασμός Χαμηλής Τάσης-Ηλεκτρικής Ενέργειας"
ISSUE_DATE = r"^(\d{2}/\d{2}/\d{4})$"  # η πρώτη «σκέτη» ημερομηνία είναι η έκδοση
# Το € δεν μπαίνει πάντα: ο «Τελικός Εκκαθαριστικός» γράφει σκέτο «-208,37»
GAS_TOTAL = rf"Σύνολο Τρέχοντος Λογαριασμού\s*({NUMBER})\s*€?"
POWER_TOTAL = rf"ΣΥΝΟΛΟ ΛΟΓΑΡΙΑΣΜΟΥ:\s*({NUMBER})\s*€?"


def matches(text: str) -> bool:
    return "nrg" in text.lower() and (GAS_TITLE in text or POWER_TITLE in text)


def parse(text: str) -> Bill:
    issue_date = find(ISSUE_DATE, text)
    if GAS_TITLE in text:
        kind = "gas"
        kwh = find(rf"^kWh\n({NUMBER})$", text)
        kwh = gr_number(kwh) if kwh is not None else None
        amount = find(GAS_TOTAL, text)
    else:
        kind = "revma"
        charges = re.findall(r"Χρέωση [^:\n]*Ενέργειας: (\d+)kWhX", text)
        kwh = sum(Decimal(c) for c in charges) if charges else None
        amount = find(POWER_TOTAL, text)

    return make_bill("NRG", kind, issue_date, kwh, amount)
