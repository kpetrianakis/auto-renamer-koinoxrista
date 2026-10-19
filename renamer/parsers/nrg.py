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
