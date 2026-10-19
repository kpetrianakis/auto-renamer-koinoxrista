from pathlib import Path

DEFAULT_ROOT = Path(r"C:\Users\me\OneDrive\Κοινόχρηστα")

# Φάκελος -> τύπος λογαριασμού που περιμένουμε να περιέχει
FOLDER_KINDS = {
    "Λογαριασμοι Αεριου": "gas",
    "Λογαριασμοι Ρευματος": "revma",
}

LOG_NAME = "auto-renamer.log"
RESCAN_SECONDS = 600
SETTLE_SECONDS = 5.0
