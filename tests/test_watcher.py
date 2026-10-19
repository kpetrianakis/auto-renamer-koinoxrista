import shutil
import threading
import time

from renamer.scanner import Scanner
from renamer.watcher import run_watcher

TARGET = "NRG revma 2026.10.09 66kwh euro 82.12.pdf"


def wait_for(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.2)
    return False


def test_new_file_is_renamed_while_watching(fixtures_dir, tmp_path):
    power = tmp_path / "Λογαριασμοι Ρευματος"
    power.mkdir()
    scanner = Scanner([power], settle_seconds=0.5)
    stop = threading.Event()
    thread = threading.Thread(target=run_watcher, args=(scanner,), kwargs=dict(rescan_seconds=600, stop=stop))
    thread.start()
    try:
        time.sleep(1)  # ο observer ξεκινά
        shutil.copy(fixtures_dir / "power_2026_10.pdf", power / "download.pdf")
        assert wait_for(lambda: (power / TARGET).exists())
        time.sleep(2)  # το δικό μας rename δεν πρέπει να προκαλέσει νέα μετονομασία
        assert [p.name for p in power.iterdir()] == [TARGET]
    finally:
        stop.set()
        thread.join(timeout=10)
    assert not thread.is_alive()


def test_initial_scan_picks_up_existing_files(fixtures_dir, tmp_path):
    power = tmp_path / "Λογαριασμοι Ρευματος"
    power.mkdir()
    shutil.copy2(fixtures_dir / "power_2026_10.pdf", power / "old.pdf")  # copy2: παλιό mtime
    stop = threading.Event()
    thread = threading.Thread(
        target=run_watcher, args=(Scanner([power], settle_seconds=0.5),), kwargs=dict(rescan_seconds=600, stop=stop)
    )
    thread.start()
    try:
        assert wait_for(lambda: (power / TARGET).exists())
    finally:
        stop.set()
        thread.join(timeout=10)
