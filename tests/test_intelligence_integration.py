"""Synthetic protocol and license fixtures; no protected content or real SSH writes."""

import base64
import hashlib
import json
import subprocess
import sys
import time
import zipfile
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_intelligence import archive, component, import_rows, wait
from test_intelligence import library as fixture_library

import backend.curated_sources as curated
import backend.official_catalogs as official
from backend.core_profiles import configured_core
from backend.db import CatalogRun, Game, GameInsight, SyncPresence, SyncRun
from backend.intelligence_schemas import OfficialCatalog
from backend.scanner import candidate

library = fixture_library


def test_remote_bios_reader_hashes_content_without_copy_and_rejects_duplicates(tmp_path):
    from backend.intelligence import BIOS_CHECK

    payload = b"synthetic BIOS fixture only"
    path = archive(tmp_path, "neogeo", {"fixture.bin": payload})
    expected = {"neogeo": [component("fixture.bin", payload)]}

    def check():
        args = base64.b64encode(json.dumps({"root": str(tmp_path), "expected": expected}).encode()).decode()
        return json.loads(
            subprocess.run(
                [sys.executable, "-c", BIOS_CHECK, args], check=True, capture_output=True, text=True
            ).stdout
        )

    result = check()
    assert result["complete"] and result["copied"] is False
    assert list(tmp_path.iterdir()) == [path]
    expected["neogeo"][0]["sha1"] = "0" * 40
    assert not check()["complete"]
    expected["neogeo"][0]["sha1"] = hashlib.sha1(payload).hexdigest()
    with zipfile.ZipFile(path, "a") as output, pytest.warns(UserWarning, match="Duplicate name"):
        output.writestr("fixture.bin", payload)
    assert not check()["complete"]


def test_scan_cancellation_and_3000_committed_files(library, monkeypatch):
    import backend.main as main
    from backend.scanner import scan

    app, client, folder = library

    def slow(root, platform, known, checkpoint):
        for _ in range(500):
            checkpoint({"scanned_files": 1, "total_files": 3000})
            time.sleep(0.01)
        return scan(root, platform, known, checkpoint)

    monkeypatch.setattr(main, "scan", slow)
    queued = client.post("/api/imports/scan", json={"root": str(folder)}).json()
    assert client.post("/api/jobs/" + queued["id"] + "/cancel").status_code == 200

    def job(job_id):
        for _ in range(3000):
            value = client.get("/api/jobs/" + job_id).json()
            if value["status"] not in {"queued", "running", "cancelling"}:
                return value
            time.sleep(0.02)
        raise AssertionError("Job timeout")

    assert job(queued["id"])["status"] == "cancelled"
    assert client.get("/api/stats").json()["games"] == 0
    monkeypatch.setattr(main, "scan", scan)
    for index in range(3000):
        (folder / f"fixture{index}.gg").write_bytes(f"synthetic {index}".encode())
    started = time.perf_counter()
    queued = client.post("/api/imports/scan", json={"root": str(folder)}).json()
    preview = job(queued["id"])
    assert len(preview["result"]["candidates"]) == 3000
    queued = client.post(
        "/api/imports/" + queued["id"] + "/commit",
        json={"candidate_ids": list(range(3000)), "license": "CC0-1.0", "provenance": "Synthetic fixture"},
    ).json()
    result = job(queued["id"])
    assert result["status"] == "completed" and result["result"]["imported"] == 3000
    summary = client.get("/api/intelligence/summary").json()
    assert summary["local_files"] == 3000 and summary["present_files"] == 3000
    assert client.get("/api/intelligence/owned?page=2").json()["total"] == 3000
    print(f"Benchmark 3000 scan + DB commit: {time.perf_counter() - started:.2f}s")


def test_driver_metadata_uses_exact_identifiers_and_mame_bios():
    from backend.catalog_formats import normalize

    content = """struct BurnDriver BurnDrvFixture = {
    "fixture", NULL, NULL, NULL, "2026",
    "Synthetic fixture\\0", NULL, "Test", "CPS-3",
    NULL, NULL, NULL, NULL,
    BDF_GAME_WORKING, 2, HARDWARE_CAPCOM_CPS3, GBF_VSFIGHT, FBF_MISC,
    NULL
};"""
    hints = official.driver_hints(content, "d_cps3.cpp", "CPS-3")
    assert hints["fixture"]["system"] == "CPS-3" and hints["fixture"]["players"] == "2"
    assert hints["fixture"]["genre"] == "Fighting"
    assert normalize({"name": "neogeo", "runnable": "no"}, "arcade")["kind"] == "bios"


def test_sync_guard_checks_core_override_source_and_content(library):
    app, client, folder = library
    data = b"synthetic fixture"
    path = archive(folder, "demo", {"program.bin": data})
    item = candidate([path], folder, "mame-libretro")
    item.pop("entrypoints")
    with app.state.sessions.begin() as db:
        db.add(Game(**item))
    rows = [{"name": "demo", "components": [component("program.bin", data)]}]
    import_rows(client, folder, rows, core="lr-mame2003", version="0.78")
    run = client.post("/api/intelligence/validate", json={"source_id": "fixture", "game_ids": [1]}).json()
    assert wait(client, run["id"])["result"]["complete"] == 1
    audit = {
        "cores": {"lr-mame2003": {"installed": True, "version": "0.78 abc1234", "sha256": "binary"}},
        "configs": {"mame-libretro": 'lr-mame2003 = "command"\ndefault = "lr-mame2003"'},
    }
    service = app.state.intelligence
    service.audit = lambda *args: audit
    config = {"device_id": "pi", "rom_root": "/home/pi/RetroPie/roms"}
    with app.state.sessions() as db:
        game = db.get(Game, 1)
        report = service.prepare_games([game], config, object())
        assert report[0]["compatibility"] == "dat_core_matched"
        assert game._arcade_files[0]["relative"] == "demo.zip"
        audit["configs"]["all"] = 'mame-libretro_demo = "lr-fbneo"'
        with pytest.raises(ValueError, match="default remoto"):
            service.prepare_games([game], config, object())
        audit["configs"].pop("all")
        audit["cores"]["lr-mame2003"]["version"] = "0.139"
        with pytest.raises(ValueError, match="0.78"):
            service.prepare_games([game], config, object())
        audit["cores"]["lr-mame2003"]["version"] = "0.78"
    rows[0]["year"] = "2026"
    import_rows(client, folder, rows, core="lr-mame2003", version="0.78")
    assert client.get("/api/intelligence/summary").json()["validated_games"] == 0
    assert client.get("/api/intelligence/games/1").json()["validation"]["status"] == "stale"
    with app.state.sessions() as db:
        with pytest.raises(ValueError, match="DAT aggiornato"):
            service.prepare_games([db.get(Game, 1)], config, object())


def test_restart_preserves_data_and_cleans_staging(library):
    app, client, folder = library
    import_rows(client, folder, [{"name": "original"}])
    with app.state.sessions.begin() as db:
        db.add(CatalogRun(id="interrupted", kind="catalog_import", source_id="fixture", status="running"))
        path = folder / "game.gg"
        path.write_bytes(b"synthetic")
        item = candidate([path], folder, "gamegear")
        item.pop("entrypoints")
        db.add(Game(**item))
        db.flush()
        db.add(
            SyncRun(
                id="old",
                device_id="pi",
                status="completed",
                plan={"manifest": {"games": [{"id": 1, "files": item["files"]}]}},
            )
        )
    app.state.intelligence.start()
    app.state.intelligence.start()
    assert client.get("/api/intelligence/runs/interrupted").json()["status"] == "failed"
    assert client.get("/api/intelligence/summary").json()["catalog_records"] == 1
    with app.state.sessions() as db:
        assert len(list(db.scalars(select(SyncPresence)))) == 1
        assert db.get(Game, 1).sha256 == item["sha256"]
    assert client.get("/api/intelligence/owned?collection=unsynced").json()["total"] == 0


def test_core_override_resolution_and_missing_default():
    audit = {
        "configs": {
            "neogeo": 'default = "lr-fbneo"\nlr-fbneo = "command"',
            "all": 'neogeo_demo = "lr-mame2003"',
        }
    }
    assert configured_core(audit, "neogeo", "demo")[0] == "lr-mame2003"
    assert configured_core(audit, "neogeo", "different")[0] == "lr-fbneo"
    rom_path = "/home/pi/RetroPie/roms/neogeo/rlm-123/demo.zip"
    legacy = "a" + hashlib.md5(("neogeo" + rom_path + "\n").encode()).hexdigest()
    audit["configs"]["all"] = legacy + ' = "lr-mame2003"'
    assert configured_core(audit, "neogeo", "demo", rom_path=rom_path)[0] == "lr-mame2003"
    audit["configs"]["neogeo"] = 'lr-fbneo = "command"'
    assert configured_core(audit, "neogeo", "demo")[0] == ""


def test_specific_file_rights_provider_and_tamper_rejection(tmp_path, monkeypatch):
    rights = b"Permission granted for this fixture only"
    sha = hashlib.sha1(f"blob {len(rights)}\0".encode() + rights).hexdigest()
    item = {
        "id": "fixture",
        "title": "Fixture",
        "platform": "snes",
        "author": "Test",
        "year": 2026,
        "license": "MIT",
        "repo": "test/repo",
        "revision": "a" * 40,
        "file": "game.sfc",
        "rights_repo": "test/repo",
        "rights_revision": "a" * 40,
        "rights_file": "license",
        "rights_blob": sha,
        "required_text": ["Permission granted"],
        "assets_license": "CC0",
    }
    monkeypatch.setattr(curated, "CURATED", [item])
    tree = {
        "tree": [
            {"path": "game.sfc", "type": "blob", "sha": "b" * 40, "size": 10},
            {"path": "license", "type": "blob", "sha": sha},
        ]
    }

    class HTTP:
        def read(self, url, limit):
            assert not url.endswith("game.sfc"), "Provider refresh must not download the game"
            return json.dumps(tree).encode() if "/trees/" in url else rights

    result = curated.load_curated(HTTP(), tmp_path, lambda *a: None)
    assert result[0]["downloadable"] and result[0]["payload"]["git_blob_sha1"] == "b" * 40
    (tmp_path / (sha + ".rights")).write_bytes(b"changed")
    with pytest.raises(ValueError, match="modificata"):
        curated.load_curated(HTTP(), tmp_path, lambda *a: None)


def test_official_catalog_rejects_tampered_cached_metadata(tmp_path, monkeypatch):
    data = b'<datafile><game name="demo"/></datafile>'
    sha = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    target = tmp_path / "catalogs"
    target.mkdir()
    (target / (sha + ".xml")).write_bytes(b"changed")

    class HTTP:
        def read(self, url, limit):
            return json.dumps(
                {"tree": [{"path": "metadata/mame2003.xml", "type": "blob", "sha": sha, "size": len(data)}]}
                if "/trees/" in url
                else {"sha": "a" * 40}
            ).encode()

        def close(self):
            pass

    monkeypatch.setattr(official, "PublicHTTP", HTTP)
    with pytest.raises(ValueError, match="Cache DAT modificata"):
        official.fetch_catalog(
            SimpleNamespace(data_dir=tmp_path), OfficialCatalog(provider="mame2003"), "run"
        )


def test_test_evidence_bound_to_hash_and_actual_file_counts(library):
    app, client, folder = library
    path = folder / "demo.gg"
    path.write_bytes(b"synthetic")
    item = candidate([path], folder, "gamegear")
    item.pop("entrypoints")
    with app.state.sessions.begin() as db:
        db.add(Game(**item))
        db.flush()
        db.add(GameInsight(game_id=1, test_status="passed", test_evidence={"sha256": "stale"}))
    assert client.get("/api/intelligence/summary").json()["tested_games"] == 0
    assert client.get("/api/intelligence/owned?collection=tested").json()["total"] == 0
    path.unlink()
    summary = client.get("/api/intelligence/summary").json()
    assert summary["present_files"] == 0 and summary["missing_files"] == 1 and summary["local_files"] == 1
