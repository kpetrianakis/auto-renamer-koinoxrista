import logging
import time
from pathlib import Path

from .naming import is_processed
from .processor import Result, process_file

log = logging.getLogger("renamer")

# Οριστικά αποτελέσματα: δεν ξαναεξετάζονται μέχρι να αλλάξει το αρχείο (mtime)
FINAL = {"unrecognized", "error"}


def is_settled(path: Path, seconds: float) -> bool:
    try:
        return time.time() - path.stat().st_mtime >= seconds
    except FileNotFoundError:
        return False


class Scanner:
    def __init__(self, dirs: list[Path], *, dry_run: bool = False, settle_seconds: float = 5.0):
        self.dirs = dirs
        self.dry_run = dry_run
        self.settle_seconds = settle_seconds
        # κλειδί (mtime, size): αντιγραφές κρατούν το παλιό mtime ενώ το αρχείο μεγαλώνει
        self._final: dict[Path, tuple[float, int]] = {}
        self._locked: dict[Path, tuple[float, int]] = {}

    def scan_all(self) -> list[Result]:
        results = []
        for directory in self.dirs:
            if not directory.is_dir():
                log.error("Ο φάκελος δεν υπάρχει: %s", directory)
                continue
            for path in sorted(directory.iterdir()):
                if path.is_file() and is_settled(path, self.settle_seconds):
                    result = self.handle(path)
                    if result is not None:
                        results.append(result)
        return results

    def handle(self, path: Path) -> Result | None:
        if path.suffix.lower() != ".pdf" or is_processed(path.name):
            return None
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        version = (stat.st_mtime, stat.st_size)
        if self._final.get(path) == version:
            return None

        try:
            result = process_file(path, dry_run=self.dry_run)
        except Exception as exc:  # ένα «περίεργο» αρχείο δεν σταματά τη σάρωση των υπολοίπων
            result = Result("error", path, message=f"απρόσμενο σφάλμα: {exc!r}")
        if result.status in FINAL:
            self._final[path] = version
        if result.status == "locked":
            if self._locked.get(path) == version:
                return result  # ήδη καταγραμμένο· απλώς ξαναδοκιμάζουμε σιωπηλά
            self._locked[path] = version
        _log(result)
        return result


def _log(result: Result) -> None:
    name = result.source.name
    if result.status in ("renamed", "would_rename"):
        prefix = "[dry-run] " if result.status == "would_rename" else ""
        log.info("%sΜετονομασία: %s → %s", prefix, name, result.target.name)
        if result.message:
            log.warning("Λάθος φάκελος: %s (%s)", result.target.name, result.message)
    elif result.status == "unrecognized":
        log.info("Μη αναγνωρισμένο PDF, μένει ως έχει: %s", name)
    elif result.status == "error":
        log.warning("Σφάλμα στο %s: %s", name, result.message)
    elif result.status == "locked":
        log.info("Θα ξαναδοκιμαστεί αργότερα: %s (%s)", name, result.message)
