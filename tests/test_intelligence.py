import csv
import hashlib
import json
import stat
import time
import zipfile
from types import SimpleNamespace

import py7zr
import pytest
from defusedxml.common import DefusedXmlException
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.arcade_archives import inspect_archive, validate_set
from backend.catalog_formats import normalize, records
from backend.core_profiles import compatible
from backend.db import CatalogEntry, Device, Game
from backend.intelligence import Cancelled
from backend.main import create_app
from backend.scanner import candidate, scan


def component(name, content, **values):
    return {
        "name": name,
        "size": len(content),
        "sha1": hashlib.sha1(content).hexdigest(),
        "sha256": hashlib.sha256(content).hexdigest(),
        **values,
    }


def archive(folder, name, files):
    path = folder / (name + ".zip")
    with zipfile.ZipFile(path, "w") as output:
        for filename, content in files.items():
            output.writestr(filename, content)
    return path


def entry(name, parts, **values):
    return normalize({"name": name, "components": parts, **values}, "arcade")


def wait(client, run_id):
    for _ in range(800):
        value = client.get("/api/intelligence/runs/" + run_id).json()
        if value["status"] not in {"running", "queued", "cancelling"}:
            return value
        time.sleep(0.02)
    raise AssertionError("Intelligence operation timed out")


@pytest.fixture
def library(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    app = create_app(tmp_path / "data")
    with TestClient(app, headers={"X-RLM-Request": "1"}) as client:
        assert (
            client.put(
                "/api/settings", json={"import_roots": [str(source)], "export_root": str(source)}
            ).status_code
            == 200
        )
        yield app, client, source


def import_rows(client, folder, rows, source="fixture", **options):
    path = folder / (source + ".json")
    path.write_text(json.dumps(rows), encoding="utf-8")
    response = client.post(
        "/api/intelligence/imports",
        json={"source_id": source, "name": source, "path": str(path), "platform": "arcade", **options},
    )
    assert response.status_code == 202, response.text
    run = wait(client, response.json()["id"])
    assert run["status"] == "completed", run
    return run


def test_xml_dat_csv_json_streaming_and_metadata(tmp_path):
    payload = b"fixture"
    sha = hashlib.sha1(payload).hexdigest()
    xml = tmp_path / "games.xml"
    xml.write_text(
        f'''<?xml version="1.0"?><!DOCTYPE mame [<!ELEMENT mame ANY>]><mame build="0.78"><machine name="demo" romof="neogeo"><description>A &amp; B</description><year>1999?</year><manufacturer>Maker</manufacturer><input players="2"><control type="joystick"/></input><display rotate="90"/><rom name="program.bin" size="7" sha1="{sha}"/></machine></mame>'''
    )
    header = {}
    values = list(records(xml, "auto", "arcade", header))
    assert values[0]["title"] == "A & B" and values[0]["platform"] == "neogeo"
    assert values[0]["players"] == 2 and values[0]["orientation"] == "90" and header["build"] == "0.78"
    dat = tmp_path / "games.dat"
    dat.write_text(
        f'clrmamepro (name "Fixture" version "0.78") game (name demo description "Demo ü" rom (name program.bin size 7 sha1 {sha}))',
        encoding="utf-8",
    )
    assert list(records(dat, "auto", "arcade", {}))[0]["components"][0]["sha1"] == sha
    structured = tmp_path / "games.json"
    structured.write_text(json.dumps([{"name": "x", "components": [component("x.bin", payload)]}]))
    assert list(records(structured, "json", "nes", {}))[0]["platform"] == "nes"
    csvfile = tmp_path / "games.csv"
    with csvfile.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["name", "title", "components"])
        writer.writeheader()
        writer.writerow(
            {"name": "csv", "title": "Titolo ü", "components": json.dumps([component("a.bin", payload)])}
        )
    assert list(records(csvfile, "csv", "snes", {}))[0]["title"] == "Titolo ü"


def test_xml_entities_and_unsafe_component_names(tmp_path):
    path = tmp_path / "evil.xml"
    path.write_text(
        '<!DOCTYPE mame [<!ENTITY x SYSTEM "file:///etc/passwd">]><mame><game name="a"><description>&x;</description></game></mame>'
    )
    with pytest.raises(DefusedXmlException):
        list(records(path, "xml", "arcade", {}))
    for name in ["../x", "/x", "C:/x", "a/../../x"]:
        with pytest.raises(ValueError):
            entry("test", [component(name, b"x")])


@pytest.mark.parametrize("mode", ["split", "merged", "non-merged", "full-non-merged"])
def test_parent_clone_bios_set_modes(tmp_path, mode):
    shared = b"parent payload"
    unique = b"clone payload"
    bios = b"authorized synthetic BIOS fixture"
    catalog = {
        "bios": entry("bios", [component("bios.bin", bios)], kind="bios"),
        "parent": entry("parent", [component("shared.bin", shared)], romof="bios"),
        "clone": entry(
            "clone",
            [component("shared.bin", shared, merge="shared.bin"), component("clone.bin", unique)],
            parent="parent",
            romof="bios",
        ),
    }
    parent_files = {"shared.bin": shared}
    clone_files = {"clone.bin": unique}
    if mode in {"non-merged", "full-non-merged"}:
        clone_files["shared.bin"] = shared
    if mode == "full-non-merged":
        clone_files["bios.bin"] = bios
    if mode == "merged":
        parent_files["clone/clone.bin"] = unique
    paths = {
        "parent": archive(tmp_path, "parent", parent_files),
        "clone": archive(tmp_path, "clone", clone_files),
        "bios": archive(tmp_path, "bios", {"bios.bin": bios}),
    }
    result = validate_set(catalog["clone"], catalog, paths, mode)
    assert result["status"] == "complete", result["problems"]
    assert result["launchable"] == (mode != "merged")
    if mode != "full-non-merged":
        paths.pop("bios")
        assert validate_set(catalog["clone"], catalog, paths, mode)["status"] == "incomplete"


def test_component_names_size_hash_and_unknown_dumps(tmp_path):
    game = entry("demo", [component("program.bin", b"correct")])
    for files in [{"other.bin": b"correct"}, {"program.bin": b"corrupt"}, {"program.bin": b"correct-long"}]:
        result = validate_set(game, {"demo": game}, {"demo": archive(tmp_path, "demo", files)}, "non-merged")
        assert result["status"] == "incomplete"
    game = entry("demo", [{"name": "unknown", "size": 5, "status": "nodump"}])
    assert validate_set(game, {"demo": game}, {}, "non-merged")["status"] == "incomplete"


def test_zip_security_and_7z_hashing_without_disk_extraction(tmp_path):
    for name in ["../evil", "C:/evil", "/evil"]:
        path = archive(tmp_path, "bad", {name: b"x"})
        with pytest.raises(ValueError):
            inspect_archive(path)
    path = tmp_path / "link.zip"
    with zipfile.ZipFile(path, "w") as output:
        info = zipfile.ZipInfo("link")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        output.writestr(info, b"/etc/passwd")
    with pytest.raises(ValueError):
        inspect_archive(path)
    path = tmp_path / "ok.7z"
    payload = b"synthetic archive content" * 200
    with py7zr.SevenZipFile(path, "w") as output:
        output.writestr(payload, "dati ü/program.bin")
    result = inspect_archive(path)
    assert result["dati ü/program.bin"]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert not (tmp_path / "dati ü").exists()


def test_mass_catalog_10000_pagination_search_incremental(library):
    app, client, folder = library
    rows = [
        {
            "name": f"set{i:05}",
            "title": f"Catalog game {i:05}",
            "parent": f"set{i - 1:05}" if i % 2 else "",
            "players": 2 if i % 3 else 1,
        }
        for i in range(10000)
    ]
    start = time.perf_counter()
    run = import_rows(client, folder, rows)
    assert run["result"]["records"] == 10000
    summary = client.get("/api/intelligence/summary").json()
    assert (
        summary["catalog_records"] == 10000
        and summary["unique_families"] == 5000
        and summary["local_files"] == 0
    )
    response = client.post("/api/intelligence/search?page=2&page_size=30", json={}).json()
    assert response["total"] == 10000 and len(response["items"]) == 30
    assert all("components" not in item for item in response["items"])
    start_search = time.perf_counter()
    found = client.post("/api/intelligence/search", json={"q": "09999"}).json()
    assert found["total"] == 1
    search_seconds = time.perf_counter() - start_search
    unchanged = import_rows(client, folder, rows)
    assert unchanged["result"]["unchanged_file"]
    rows[10]["title"] = "Updated title"
    rows.append({"name": "new", "title": "New"})
    changed = import_rows(client, folder, rows)
    assert (
        changed["result"]["changed"] == 1
        and changed["result"]["added"] == 1
        and changed["result"]["unchanged"] == 9999
    )
    assert client.post("/api/intelligence/search", json={"q": "Updated"}).json()["total"] == 1
    print(
        f"Benchmark 10000: initial={run['result']['seconds']}s search={search_seconds:.4f}s complete={time.perf_counter() - start:.2f}s"
    )


def test_failed_cancelled_import_preserves_active_catalog(library, monkeypatch):
    app, client, folder = library
    import_rows(client, folder, [{"name": "keep"}])
    original = app.state.intelligence.checkpoint

    def cancel(run_id, progress=None):
        if progress and progress.get("records", 0) >= 250:
            raise Cancelled()
        original(run_id, progress)

    monkeypatch.setattr(app.state.intelligence, "checkpoint", cancel)
    path = folder / "cancel.json"
    path.write_text(json.dumps([{"name": f"x{i}"} for i in range(1000)]))
    run = client.post(
        "/api/intelligence/imports", json={"source_id": "fixture", "name": "fixture", "path": str(path)}
    ).json()
    assert wait(client, run["id"])["status"] == "cancelled"
    assert client.get("/api/intelligence/summary").json()["catalog_records"] == 1
    monkeypatch.setattr(app.state.intelligence, "checkpoint", original)
    path.write_text('[{"name":"x"}, malformed')
    run = client.post(
        "/api/intelligence/imports", json={"source_id": "fixture", "name": "fixture", "path": str(path)}
    ).json()
    assert wait(client, run["id"])["status"] == "failed"
    assert client.post("/api/intelligence/search", json={"q": "keep"}).json()["total"] == 1
    with app.state.sessions() as db:
        assert len(list(db.scalars(select(CatalogEntry)))) == 1


def test_core_revision_compatibility():
    source = SimpleNamespace(config={"core": "lr-mame2003", "version": "0.78"}, sha256="dat")
    observed = {"installed": True, "version": "0.78 abc1234", "sha256": "binary"}
    assert compatible(source, "lr-mame2003", observed)[0]
    source.config["version"] = "0.139"
    assert not compatible(source, "lr-mame2003", observed)[0]
    source.config = {"core": "lr-fbneo", "version": "1.0.0.03"}
    observed["version"] = "v1.0.0.03 af50579"
    assert not compatible(source, "lr-fbneo", observed)[0]
    revision = "af50579270a610eda8ac580648d9c12acc7bb565"
    source.config.update(
        official_verified=True,
        revision=revision,
        source_url="https://raw.githubusercontent.com/libretro/FBNeo/" + revision + "/dats/example.dat",
    )
    assert compatible(source, "lr-fbneo", observed)[0]
    observed["version"] = "v1.0.0.03 deadbee"
    assert not compatible(source, "lr-fbneo", observed)[0]


def test_api_validation_export_gating_metadata_and_evidence(library):
    app, client, folder = library
    payload = b"legitimate synthetic data"
    path = archive(folder, "fixture", {"program.bin": payload})
    item = candidate([path], folder, "arcade")
    item.pop("entrypoints")
    with app.state.sessions.begin() as db:
        db.add(Game(**item, license="CC0-1.0", provenance="Synthetic"))
        db.add(Device(id="pi", config={"host": "test"}, fingerprint="", is_default=True))
    response = client.post("/api/exports", json={"game_ids": [1], "dry_run": True}).json()
    for _ in range(100):
        job = client.get("/api/jobs/" + response["id"]).json()
        if job["status"] not in ["queued", "running"]:
            break
        time.sleep(0.02)
    assert job["status"] == "failed" and "validare" in job["error"]
    import_rows(
        client,
        folder,
        [
            {
                "name": "fixture",
                "description": "Readable title",
                "manufacturer": "Author",
                "components": [component("program.bin", payload)],
            }
        ],
        core="lr-mame2003",
        version="0.78",
    )
    run = client.post(
        "/api/intelligence/validate", json={"source_id": "fixture", "game_ids": [1], "mode": "non-merged"}
    ).json()
    assert wait(client, run["id"])["result"]["complete"] == 1
    assert client.get("/api/intelligence/summary").json()["validated_games"] == 1
    run = client.post(
        "/api/intelligence/metadata", json={"source_id": "fixture", "game_ids": [1], "apply": True}
    ).json()
    assert wait(client, run["id"])["status"] == "completed"
    assert client.get("/api/games/1").json()["title"] == "Readable title"
    body = {
        "confirmed": True,
        "test_status": "passed",
        "device_id": "pi",
        "evidence": "Test reported by the user on actual hardware",
    }
    assert client.put("/api/intelligence/games/1", json={**body, "evidence": ""}).status_code == 400
    assert client.put("/api/intelligence/games/1", json=body).status_code == 200
    assert client.get("/api/intelligence/summary").json()["tested_games"] == 1
    assert client.get("/api/intelligence/owned?collection=tested").json()["total"] == 1
    with app.state.sessions() as db:
        game = db.get(Game, 1)
        app.state.intelligence.prepare_games([game])
        assert game._arcade_files[0]["relative"] == "fixture.zip"
    path.write_bytes(b"changed")
    with app.state.sessions() as db:
        with pytest.raises(ValueError):
            app.state.intelligence.prepare_games([db.get(Game, 1)])


def test_3000_local_files_deduplication(tmp_path):
    for index in range(3000):
        (tmp_path / f"game{index}.gg").write_bytes(("synthetic " + str(index)).encode())
    start = time.perf_counter()
    result = scan(tmp_path, None, set())
    assert len(result["candidates"]) == 3000 and not result["warnings"]
    repeated = scan(tmp_path, None, {c["sha256"] for c in result["candidates"]})
    assert all(c["duplicate"] for c in repeated["candidates"])
    print(f"Benchmark 3000 local files scan+repeat: {time.perf_counter() - start:.2f}s")


def test_import_duplicate_conflict_and_parent_cycle(library):
    app, client, folder = library
    run = import_rows(client, folder, [{"name": "same"}, {"name": "same"}])
    assert run["result"]["records"] == 1 and run["result"]["duplicates"] == 1
    for rows in [
        [{"name": "same", "title": "A"}, {"name": "same", "title": "B"}],
        [{"name": "a", "parent": "b"}, {"name": "b", "parent": "a"}],
    ]:
        path = folder / "invalid.json"
        path.write_text(json.dumps(rows))
        run = client.post(
            "/api/intelligence/imports", json={"source_id": "fixture", "name": "fixture", "path": str(path)}
        ).json()
        assert wait(client, run["id"])["status"] == "failed"
        assert client.get("/api/intelligence/summary").json()["catalog_records"] == 1
