import os
import shutil
import time

import pytest

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


def test_watcher_crash_is_retried(tmp_path, monkeypatch):
    import renamer.__main__ as main_mod

    calls = []

    def fake_run_watcher(scanner, **kw):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("observer died")
        raise KeyboardInterrupt

    monkeypatch.setattr(main_mod, "run_watcher", fake_run_watcher)
    monkeypatch.setattr(main_mod.time, "sleep", lambda s: None)
    assert main(["--root", str(tmp_path)]) == 0
    assert len(calls) == 2


def test_root_from_environment(tmp_path, fixtures_dir, monkeypatch, capsys):
    make_root(tmp_path, fixtures_dir)
    monkeypatch.setenv("KOINOXRISTA_ROOT", str(tmp_path))
    assert main(["--dry-run"]) == 0
    assert "x.pdf → NRG revma" in capsys.readouterr().err


def test_missing_root_is_an_error(monkeypatch, capsys):
    monkeypatch.delenv("KOINOXRISTA_ROOT", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["--dry-run"])
    assert exc.value.code == 2
    assert "KOINOXRISTA_ROOT" in capsys.readouterr().err
