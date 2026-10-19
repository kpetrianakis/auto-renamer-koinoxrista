# auto-renamer-koinoxrista

Watcher για Windows που μετονομάζει αυτόματα λογαριασμούς ρεύματος και φυσικού
αερίου (PDF) με στοιχεία που διαβάζει από το ίδιο το PDF:

```
NRG gas 2026.10.16 0kwh euro 16.78.pdf
NRG revma 2026.10.09 66kwh euro 82.12.pdf
```

*Windows watcher that renames electricity/gas bill PDFs (Greek provider NRG)
to `<provider> <type> <issue date> <kWh>kwh euro <amount>.pdf`.*

## Πώς δουλεύει

1. Το `watchdog` ειδοποιείται όταν μπαίνει ή μετονομάζεται αρχείο στους δύο
   φακέλους. Επιπλέον, κάθε 10 λεπτά γίνεται σάρωση ασφαλείας, για αρχεία που
   φέρνει το OneDrive χωρίς γεγονός.
2. Κάθε PDF επεξεργάζεται μόνο όταν το αρχείο έχει σταματήσει να αλλάζει για
   5 δευτερόλεπτα.
3. Το PyMuPDF εξάγει το κείμενο του PDF και ένας parser ανά πάροχο
   (`renamer/parsers/`) βρίσκει:
   - **ημερομηνία έκδοσης**,
   - **kWh**: στο αέριο από τον πίνακα κατανάλωσης, στο ρεύμα ως άθροισμα των
     χρεώσεων ενέργειας,
   - **ποσό τρέχοντος λογαριασμού**.
4. Το αρχείο μετονομάζεται επιτόπου.

Κανόνες ασφαλείας:
- **Ποτέ δεν αντικαθίσταται αρχείο.** Αν το όνομα υπάρχει ήδη, προστίθεται
  ` (2)`, ` (3)` κ.λπ.
- Αρχεία που έχουν ήδη το σωστό όνομα δεν ανοίγονται καθόλου.
- PDF που δεν είναι λογαριασμός (π.χ. σύμβαση) μένει ανέγγιχτο και γράφεται
  στο log μία φορά.
- Κλειδωμένο αρχείο (συγχρονισμός OneDrive) → ξαναδοκιμάζεται αργότερα.
- Λογαριασμός σε λάθος φάκελο → μετονομάζεται με βάση το περιεχόμενο και
  γράφεται προειδοποίηση στο log.

## Εγκατάσταση

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.\install_task.ps1 -Root 'C:\Users\<user>\OneDrive\Κοινόχρηστα'
```

Ο φάκελος-ρίζα πρέπει να περιέχει τους υποφακέλους `Λογαριασμοι Αεριου` και
`Λογαριασμοι Ρευματος`. Το `install_task.ps1` καταχωρεί εργασία στον Task
Scheduler που ξεκινά τον watcher (χωρίς παράθυρο) σε κάθε login.

## Χειροκίνητη χρήση

```powershell
$env:KOINOXRISTA_ROOT = 'C:\...\Κοινόχρηστα'   # ή --root
.venv\Scripts\python -m renamer --dry-run        # τι θα άλλαζε, χωρίς αλλαγές
.venv\Scripts\python -m renamer --once           # μία σάρωση
.venv\Scripts\python -m renamer                  # watcher
```

Log: `auto-renamer.log` στον φάκελο-ρίζα.

## Tests

```powershell
.venv\Scripts\python -m pytest
```

Τα PDF του `tests/fixtures/` είναι συνθετικά (`python tests/make_fixtures.py`).
Πραγματικοί λογαριασμοί μπορούν να μπουν τοπικά στο `tests/fixtures/private/`
(gitignored), με όνομα το αναμενόμενο αποτέλεσμα, και ελέγχονται αυτόματα.

## Νέος πάροχος

Πρόσθεσε ένα module στο `renamer/parsers/` με δύο συναρτήσεις:
- `matches(text) -> bool`
- `parse(text) -> Bill`

Δήλωσέ το στο `PARSERS` του `renamer/parsers/__init__.py` και πρόσθεσε το
όνομα του παρόχου στο `PROCESSED_RE` του `renamer/naming.py`.

Λεπτομέρειες σχεδίασης: [`docs/superpowers/specs/`](docs/superpowers/specs/).
