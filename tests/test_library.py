import hashlib
import json
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.paths import reference
from backend.providers import download, validate_url
from backend.scanner import scan
from backend.schemas import DownloadEntry


@pytest.fixture
def library(tmp_path):
    source = tmp_path / "roms"
    destination = tmp_path / "exports"
    source.mkdir()
    destination.mkdir()
    app = create_app(tmp_path / "data")
    with TestClient(app, headers={"X-RLM-Request": "1"}) as client:
        assert (
            client.put(
                "/api/settings", json={"import_roots": [str(source)], "export_root": str(destination)}
            ).status_code
            == 200
        )
        yield client, source, destination


def completed(client, response, expected="completed"):
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        result = client.get(f"/api/jobs/{job_id}").json()
        if result["status"] in {"completed", "failed"}:
            assert result["status"] == expected, result
            return result
        time.sleep(0.05)
    pytest.fail("Job timed out")


def import_all(client, source):
    preview = completed(client, client.post("/api/imports/scan", json={"root": str(source)}))
    ids = [c["id"] for c in preview["result"]["candidates"]]
    result = completed(
        client, client.post(f"/api/imports/{preview['id']}/commit", json={"candidate_ids": ids})
    )
    return preview, result


def test_catalog_import_edit_filter_export(library):
    client, source, destination = library
    original = b"synthetic test fixture, no game data"
    (source / "Demo (Europe).nes").write_bytes(original)
    (source / "Copy.nes").write_bytes(original)
    preview, imported = import_all(client, source)
    assert imported["result"] == {"imported": 1, "skipped": 1}
    assert sum(c["duplicate"] for c in preview["result"]["candidates"]) == 1
    item = client.get("/api/games").json()["items"][0]
    assert item["sha256"] == hashlib.sha256(original).hexdigest()
    client.patch(f"/api/games/{item['id']}/favorite", json={"favorite": True})
    assert client.get("/api/games?favorite=true").json()["total"] == 1
    assert client.get("/api/games?q=not-present").json()["total"] == 0
    assert client.get("/api/games?platform=psx").json()["total"] == 0
    assert client.get("/api/stats").json()["favorites"] == 1
    edited = {
        "title": "Edited",
        "year": 1992,
        "genre": "Puzzle",
        "description": "Test description",
        "license": "Test-only fixture",
    }
    assert client.put(f"/api/games/{item['id']}", json=edited).status_code == 200
    assert client.get("/api/games?genre=Puzzle").json()["total"] == 1
    dry = completed(client, client.post("/api/exports", json={"game_ids": [item["id"]]}))
    assert dry["result"]["dry_run"] is True
    assert not list(destination.iterdir())
    result = completed(client, client.post("/api/exports", json={"game_ids": [item["id"]], "dry_run": False}))
    final = Path(result["result"]["destination"])
    manifest = json.loads((final / "manifest.json").read_text())
    assert (final / manifest["games"][0]["files"][0]["path"]).read_bytes() == original
    assert (source / "Demo (Europe).nes").read_bytes() == original
    assert dry["result"]["required_bytes"] == sum(p.stat().st_size for p in final.rglob("*") if p.is_file())


def test_multidisc_cue_playlist_and_duplicates(library):
    client, source, _ = library
    for disc in (1, 2):
        (source / f"Adventure (Disc {disc}).bin").write_bytes(f"synthetic disc {disc}".encode())
        (source / f"Adventure (Disc {disc}).cue").write_text(
            f'FILE "Adventure (Disc {disc}).bin" BINARY\n TRACK 01 MODE2/2352\n INDEX 01 00:00:00\n'
        )
    preview, _ = import_all(client, source)
    assert len(preview["result"]["candidates"]) == 1
    game = client.get("/api/games").json()["items"][0]
    assert len(game["files"]) == 4
    assert game["format"] == "multidisc"
    result = completed(client, client.post("/api/exports", json={"game_ids": [game["id"]], "dry_run": False}))
    final = Path(result["result"]["destination"])
    playlist = final / result["result"]["manifest"]["games"][0]["launch"]
    assert len(playlist.read_text().splitlines()) == 2
    assert result["result"]["required_bytes"] == sum(
        p.stat().st_size for p in final.rglob("*") if p.is_file()
    )
    for line in playlist.read_text().splitlines():
        assert (playlist.parent / line).exists()


def test_m3u_nested_tracks(tmp_path):
    discs = tmp_path / "disc"
    discs.mkdir()
    (discs / "track.bin").write_bytes(b"fake track")
    (discs / "game.cue").write_text('FILE "track.bin" BINARY\n')
    (tmp_path / "game.m3u").write_text("disc/game.cue\n")
    result = scan(tmp_path, None, set())
    assert len(result["candidates"]) == 1
    assert len(result["candidates"][0]["files"]) == 3


def test_mutated_source_rolls_back_import(library):
    client, source, _ = library
    (source / "A.nes").write_bytes(b"A")
    (source / "B.nes").write_bytes(b"B")
    preview = completed(client, client.post("/api/imports/scan", json={"root": str(source)}))
    (source / "B.nes").write_bytes(b"changed")
    completed(
        client, client.post(f"/api/imports/{preview['id']}/commit", json={"candidate_ids": [0, 1]}), "failed"
    )
    assert client.get("/api/games").json()["total"] == 0


def test_repeated_import_idempotent_and_export_mutation(library):
    client, source, destination = library
    path = source / "Test.gba"
    path.write_bytes(b"fixture")
    preview, _ = import_all(client, source)
    repeated = completed(
        client, client.post(f"/api/imports/{preview['id']}/commit", json={"candidate_ids": [0]})
    )
    assert repeated["result"]["imported"] == 0
    game = client.get("/api/games").json()["items"][0]
    path.write_bytes(b"changed")
    completed(
        client, client.post("/api/exports", json={"game_ids": [game["id"]], "dry_run": False}), "failed"
    )
    assert not list(destination.iterdir())


@pytest.mark.parametrize(
    "name", ["../outside.bin", "C:/secret.bin", "/etc/passwd", "nested/../../file", "file:stream"]
)
def test_traversal_rejected(tmp_path, name):
    with pytest.raises((ValueError, OSError)):
        reference(tmp_path, name, tmp_path)


def test_cue_escape_missing_and_ambiguous(library):
    client, source, _ = library
    (source / "bad.cue").write_text('FILE "../secret.bin" BINARY\n')
    (source / "missing.cue").write_text('FILE "absent.bin" BINARY\n')
    (source / "orphan.bin").write_bytes(b"fixture")
    (source / "unknown.zip").write_bytes(b"fixture archive")
    result = completed(client, client.post("/api/imports/scan", json={"root": str(source)}))["result"]
    assert not result["candidates"]
    assert len(result["warnings"]) == 4


def test_api_validation_and_origin(library):
    client, source, _ = library
    assert client.post("/api/imports/scan", json={"root": str(source.parent)}).status_code == 400
    assert (
        client.post("/api/imports/scan", json={"root": str(source), "platform": "invalid"}).status_code == 422
    )
    assert client.get("/api/games?page_size=9999").status_code == 422
    assert client.get("/api/games/999").status_code == 404
    assert client.put("/api/settings", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.put("/api/settings", json={}, headers={"X-RLM-Request": ""}).status_code == 403
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400


def test_pagination_and_literal_search(library):
    client, source, _ = library
    for i in range(1200):
        (source / f"Game {i:02}.gb").write_bytes(f"fixture {i}".encode())
    import_all(client, source)
    first = client.get("/api/games?page_size=10").json()
    second = client.get("/api/games?page_size=10&page=2").json()
    assert first["total"] == 1200
    assert len(first["items"]) == 10
    assert {g["id"] for g in first["items"]}.isdisjoint(g["id"] for g in second["items"])
    assert client.get("/api/games?q=%25").json()["total"] == 0


def entry_for(payload):
    return DownloadEntry(
        id="demo",
        title="Fixture",
        platform="nes",
        url="https://example.org/demo.nes",
        filename="demo.nes",
        sha256=hashlib.sha256(payload).hexdigest(),
        size=len(payload),
        license="CC0-1.0",
        rights_url="https://example.org/license",
        distribution="homebrew",
        redistribution_allowed=True,
    )


@pytest.mark.parametrize("mode", ["success", "hash", "size", "redirect", "http_error"])
def test_download_integrity_cleanup(tmp_path, monkeypatch, mode):
    payload = b"synthetic download fixture"
    entry = entry_for(payload)
    monkeypatch.setattr("backend.providers.validate_url", lambda url: None)
    status = 302 if mode == "redirect" else 404 if mode == "http_error" else 200
    content = b"x" * len(payload) if mode == "hash" else payload + b"more" if mode == "size" else payload
    transport = httpx.MockTransport(lambda request: httpx.Response(status, content=content))
    if mode == "success":
        result = download(entry, tmp_path, transport)
        assert result.read_bytes() == payload
        assert download(entry, tmp_path, transport) == result
    else:
        with pytest.raises(ValueError):
            download(entry, tmp_path, transport)
        assert not list(tmp_path.iterdir())
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize(
    "url",
    ["http://example.com/a", "https://127.0.0.1/a", "https://user:password@example.com/a", "https://[::1]/a"],
)
def test_download_url_security(url):
    with pytest.raises(ValueError):
        validate_url(url)


def test_persistence_and_migration(tmp_path):
    data = tmp_path / "database"
    with TestClient(create_app(data), headers={"X-RLM-Request": "1"}) as client:
        client.put("/api/settings", json={"import_roots": [str(tmp_path)]})
    with TestClient(create_app(data)) as client:
        assert client.get("/api/settings").json()["import_roots"] == [str(tmp_path)]
        assert client.get("/api/stats").json()["games"] == 0


def test_provider_api_download_and_retry(library, monkeypatch):
    client, source, _ = library
    payload = b"authorized synthetic provider payload"
    entry = entry_for(payload)
    manifest = {"id": "author", "name": "Test author", "entries": [entry.model_dump()]}
    assert client.put("/api/providers/author", json=manifest).status_code == 200
    assert len(client.get("/api/providers").json()) == 1
    monkeypatch.setattr("backend.providers.validate_url", lambda url: None)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=payload))
    monkeypatch.setattr("backend.main.download", lambda item, directory: download(item, directory, transport))
    result = completed(client, client.post("/api/providers/author/download/demo"))
    game_id = result["result"]["game_id"]
    game = client.get(f"/api/games/{game_id}").json()
    assert game["license"] == "CC0-1.0"
    assert game["title"] == "Fixture"
    assert Path(game["local_path"]).read_bytes() == payload
    repeated = completed(client, client.post("/api/providers/author/download/demo"))
    assert repeated["result"]["duplicate"] is True
    assert client.get("/api/games").json()["total"] == 1


def test_export_partial_failure_cleanup(library, monkeypatch):
    client, source, destination = library
    (source / "Test.nes").write_bytes(b"synthetic fixture")
    import_all(client, source)
    game = client.get("/api/games").json()["items"][0]

    def broken_copy(source, target):
        target.write_bytes(b"partial data")
        raise OSError("Simulated disk failure")

    monkeypatch.setattr("backend.exports.shutil.copyfile", broken_copy)
    completed(
        client, client.post("/api/exports", json={"game_ids": [game["id"]], "dry_run": False}), "failed"
    )
    assert not list(destination.iterdir())


def test_plain_title_and_numbered_discs(tmp_path):
    for name in ["Adventure", "Adventure (Disc 1)", "Adventure (Disc 10)", "Adventure (Disc 2)"]:
        (tmp_path / f"{name}.chd").write_bytes(name.encode())
    result = scan(tmp_path, None, set())
    assert len(result["candidates"]) == 2
    group = next(c for c in result["candidates"] if c["format"] == "multidisc")
    assert group["entrypoints"] == [
        "Adventure (Disc 1).chd",
        "Adventure (Disc 2).chd",
        "Adventure (Disc 10).chd",
    ]


def test_unavailable_root_does_not_block_other_sources(library):
    client, source, _ = library
    missing = source / "unavailable"
    missing.mkdir()
    assert client.put("/api/settings", json={"import_roots": [str(missing), str(source)]}).status_code == 200
    missing.rmdir()
    (source / "Test.nes").write_bytes(b"synthetic fixture")
    result = completed(client, client.post("/api/imports/scan", json={"root": str(source)}))
    assert len(result["result"]["candidates"]) == 1
