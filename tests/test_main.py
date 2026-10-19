import os
import shutil
import time

from renamer.__main__ import main


def make_root(tmp_path, fixtures_dir):
    power = tmp_path / "Λογαριασμοι Ρευματος"
    power.mkdir()
    (tmp_path / "Λογαριασμοι Αεριου").mkdir()
    src = shutil.copy(fixtures_dir / "power_2026_10.pdf", power / "x.pdf")
    old = time.time() - 60
    os.utime(src, (old, old))
    return power


def test_dry_run_prints_plan_and_changes_nothing(tmp_path, fixtures_dir, capsys):
    power = make_root(tmp_path, fixtures_dir)
    assert main(["--dry-run", "--root", str(tmp_path)]) == 0
    assert "x.pdf → NRG revma 2026.10.09 66kwh euro 82.12.pdf" in capsys.readouterr().err
    assert [p.name for p in power.iterdir()] == ["x.pdf"]
    assert not (tmp_path / "auto-renamer.log").exists()


def test_once_renames_and_writes_log(tmp_path, fixtures_dir):
    power = make_root(tmp_path, fixtures_dir)
    assert main(["--once", "--root", str(tmp_path)]) == 0
    assert [p.name for p in power.iterdir()] == ["NRG revma 2026.10.09 66kwh euro 82.12.pdf"]
    log_text = (tmp_path / "auto-renamer.log").read_text(encoding="utf-8")
    assert "x.pdf → NRG revma" in log_text
