import logging
import queue
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .scanner import Scanner, is_settled

log = logging.getLogger("renamer")


class _Handler(FileSystemEventHandler):
    def __init__(self, events: queue.Queue):
        self.events = events

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self.events.put(Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        self.on_created(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        # π.χ. ο browser μετονομάζει .crdownload -> .pdf
        if not event.is_directory:
            self.events.put(Path(event.dest_path))


def run_watcher(scanner: Scanner, *, rescan_seconds: float, stop: threading.Event | None = None) -> None:
    stop = stop or threading.Event()
    events: queue.Queue[Path] = queue.Queue()
    observer = Observer()
    for directory in scanner.dirs:
        observer.schedule(_Handler(events), str(directory), recursive=False)
    observer.start()
    try:
        _safe(scanner.scan_all)
        pending: set[Path] = set()
        next_rescan = time.monotonic() + rescan_seconds
        while not stop.is_set():
            try:
                pending.add(events.get(timeout=1))
            except queue.Empty:
                pass
            for path in list(pending):
                if not path.exists():
                    pending.discard(path)
                elif is_settled(path, scanner.settle_seconds):
                    pending.discard(path)
                    _safe(scanner.handle, path)
            if time.monotonic() >= next_rescan:
                _safe(scanner.scan_all)
                next_rescan = time.monotonic() + rescan_seconds
    finally:
        observer.stop()
        observer.join()


def _safe(func, *args) -> None:
    """Ένα απρόσμενο σφάλμα σε ένα αρχείο δεν πρέπει να σταματήσει τον watcher."""
    try:
        func(*args)
    except Exception:
        log.exception("Απρόσμενο σφάλμα")
