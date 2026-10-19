import logging
import os
import shutil
import time

import pytest

import renamer.scanner as scanner_mod
from renamer.scanner import Scanner, is_settled


@pytest.fixture
def dirs(tmp_path):
    gas, power = tmp_path / "Λογαριασμοι Αεριου", tmp_path / "Λογαριασμοι Ρευματος"
    gas.mkdir()
    power.mkdir()
    return gas, power


def age(path, seconds=60):
    t = time.time() - seconds
    os.utime(path, (t, t))


def test_scan_all_renames_settled_files_in_both_folders(fixtures_dir, dirs):
    gas, power = dirs
    age(shutil.copy(fixtures_dir / "gas_estimate.pdf", gas / "invoice (12).pdf"))
    age(shutil.copy(fixtures_dir / "power_2026_03.pdf", power / "x.pdf"))
    results = Scanner(list(dirs), settle_seconds=5).scan_all()
    assert sorted(r.status for r in results) == ["renamed", "renamed"]
    assert (gas / "NRG gas 2026.04.29 4613kwh euro 349.79.pdf").exists()
    assert (power / "NRG revma 2026.03.13 115kwh euro 95.15.pdf").exists()


def test_scan_all_waits_for_fresh_files(fixtures_dir, dirs):
    gas, _ = dirs
    shutil.copy(fixtures_dir / "gas_estimate.pdf", gas / "fresh.pdf")  # mtime = τώρα
    assert Scanner(list(dirs), settle_seconds=5).scan_all() == []
    assert (gas / "fresh.pdf").exists()


def test_unrecognized_is_processed_once_per_version(not_a_bill, dirs, monkeypatch):
    _, power = dirs
    src = shutil.copy(not_a_bill, power / "contract.pdf")
    age(src)
    calls = []
    real = scanner_mod.process_file
    monkeypatch.setattr(scanner_mod, "process_file", lambda p, **kw: calls.append(p) or real(p, **kw))
    s = Scanner(list(dirs), settle_seconds=5)
    s.scan_all()
    s.scan_all()
    assert len(calls) == 1
    age(src, 30)  # το αρχείο άλλαξε -> ξαναεξετάζεται
    s.scan_all()
    assert len(calls) == 2


def test_locked_is_retried_but_logged_once(dirs, caplog):
    _, power = dirs
    src = power / "half.pdf"
    src.write_bytes(b"%PDF-1.7\n")
    age(src)
    s = Scanner(list(dirs), settle_seconds=5)
    with caplog.at_level(logging.INFO, logger="renamer"):
        assert s.scan_all()[0].status == "locked"
        assert s.scan_all()[0].status == "locked"
    assert sum("half.pdf" in r.getMessage() for r in caplog.records) == 1


def test_logs_rename_and_wrong_folder(fixtures_dir, dirs, caplog):
    _, power = dirs
    age(shutil.copy(fixtures_dir / "gas_settlement_zero.pdf", power / "invoice.pdf"))
    with caplog.at_level(logging.INFO, logger="renamer"):
        Scanner(list(dirs), settle_seconds=5).scan_all()
    text = caplog.text
    assert "invoice.pdf → NRG gas 2026.09.15 0kwh euro 17.34.pdf" in text
    assert "Λάθος φάκελος" in text


def test_missing_folder_is_logged_not_fatal(tmp_path, caplog):
    with caplog.at_level(logging.ERROR, logger="renamer"):
        assert Scanner([tmp_path / "nope"]).scan_all() == []
    assert "δεν υπάρχει" in caplog.text


def test_is_settled(tmp_path):
    f = tmp_path / "a.pdf"
    f.touch()
    assert not is_settled(f, 5)
    age(f)
    assert is_settled(f, 5)
    assert not is_settled(tmp_path / "missing.pdf", 5)
