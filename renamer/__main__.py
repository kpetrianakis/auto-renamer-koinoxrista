import argparse
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import config
from .scanner import Scanner
from .watcher import run_watcher

log = logging.getLogger("renamer")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="renamer", description="Μετονομασία λογαριασμών ρεύματος/αερίου")
    parser.add_argument("--once", action="store_true", help="μία σάρωση και έξοδος")
    parser.add_argument("--dry-run", action="store_true", help="μόνο εμφάνιση, χωρίς αλλαγές (υπονοεί --once)")
    parser.add_argument("--root", type=Path, default=os.environ.get(config.ROOT_ENV),
                        help=f"φάκελος κοινοχρήστων (default: ${config.ROOT_ENV})")
    args = parser.parse_args(argv)
    if args.root is None:
        parser.error(f"δώσε --root ή όρισε τη μεταβλητή {config.ROOT_ENV}")

    _setup_logging(None if args.dry_run else args.root / config.LOG_NAME)
    scanner = Scanner(
        [args.root / name for name in config.FOLDER_KINDS],
        dry_run=args.dry_run,
        settle_seconds=config.SETTLE_SECONDS,
    )
    if args.once or args.dry_run:
        scanner.scan_all()
        return 0

    log.info("Εκκίνηση watcher: %s", args.root)
    while True:
        try:
            run_watcher(scanner, rescan_seconds=config.RESCAN_SECONDS)
            break
        except KeyboardInterrupt:
            break
        except Exception:
            # ο Task Scheduler ξαναξεκινά μόνο αν αποτύχει η εκκίνηση, όχι σε crash
            log.exception("Ο watcher σταμάτησε απρόσμενα· επανεκκίνηση σε 60 δευτερόλεπτα")
            time.sleep(60)
    log.info("Τερματισμός watcher")
    return 0


def _setup_logging(log_file: Path | None) -> None:
    handlers: list[logging.Handler] = []
    if log_file is not None:
        handlers.append(RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"))
    if sys.stderr is not None:  # το pythonw.exe δεν έχει κονσόλα
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # κονσόλα cp1252
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers, force=True
    )


if __name__ == "__main__":
    sys.exit(main())
