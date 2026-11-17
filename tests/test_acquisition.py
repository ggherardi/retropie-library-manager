import hashlib
import io
import json
import threading
import time
import zipfile
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.acquisition_schemas import EnrichInput
from backend.db import DiscoveryEntry, DownloadTask, Game
from backend.discovery_sources import GitHubCatalog, identity, parse_entry
from backend.download_manager import validate_archive
from backend.main import create_app
from backend.network import PublicHTTP


@pytest.fixture
def acquisition(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app, headers={"X-RLM-Request": "1"}) as client:
        service = app.state.acquisition
        service.manager.stop.set()
        service.manager.thread.join()
        service.manager.stop.clear()
        yield client, service


def add_entry(service, payload=b"synthetic fixture", key="demo", **overrides):
    sha = hashlib.sha256(payload).hexdigest()
    values = dict(
        id=identity("test", key),
        provider_id="test",
        external_id=key,
        title=key,
        platform="gb",
        author="Fixture author",
        year=2024,
        genre="Puzzle",
        license="CC0-1.0",
        description="Synthetic metadata",
        source_url="https://example.org/rights",
        size=len(payload),
        available=True,
        downloadable=True,
        sha256=sha,
        reason="",
        payload={
            "url": "https://example.org/demo.gb",
            "filename": "demo.gb",
            "expected_sha256": sha,
            "cover": None,
            "evidence": {"url": "https://example.org/rights", "license": "CC0-1.0"},
        },
    )
    values.update(overrides)
    with service.sessions.begin() as db:
        db.add(DiscoveryEntry(**values))
    return values["id"]


def queue(client, entry_id):
    response = client.post("/api/acquisition/plans", json={"ids": [entry_id]})
    assert response.status_code == 200, response.text
    plan = response.json()
    response = client.post(f"/api/acquisition/plans/{plan['id']}/confirm", json={"confirmed": True})
    assert response.status_code == 200, response.text
    return response.json()["tasks"][0]


def network(service, monkeypatch, handler):
    monkeypatch.setattr(service.manager.http, "check", lambda url: None)
    service.manager.http.client.close()
    service.manager.http.client = httpx.Client(transport=httpx.MockTransport(handler))


def run_task(service, task_id):
    with service.sessions.begin() as db:
        task = db.get(DownloadTask, task_id)
        task.status = "running"
        task.attempts += 1
    service.manager.run(task_id)
    with service.sessions() as db:
        return db.get(DownloadTask, task_id)


def test_manual_confirmation_integrity_import_and_dedup(acquisition, monkeypatch):
    client, service = acquisition
    payload = b"synthetic game"
    entry_id = add_entry(service, payload)
    preview = client.post("/api/acquisition/plans", json={"ids": [entry_id]}).json()
    assert preview["count"] == 1
    assert client.get("/api/downloads").json()["total"] == 0
    endpoint = f"/api/acquisition/plans/{preview['id']}/confirm"
    assert client.post(endpoint, json={"confirmed": False}).status_code == 422
    task_id = client.post(endpoint, json={"confirmed": True}).json()["tasks"][0]
    assert client.post(endpoint, json={"confirmed": True}).json()["tasks"] == [task_id]
    network(service, monkeypatch, lambda request: httpx.Response(200, content=payload))
    task = run_task(service, task_id)
    assert task.status == "imported"
    game = client.get(f"/api/games/{task.game_id}").json()
    assert game["author"] == "Fixture author"
    assert game["description"] == "Synthetic metadata"
    assert Path(game["local_path"]).read_bytes() == payload
    assert (Path(game["local_path"]).parent / "authorization.json").exists()
    assert client.post("/api/acquisition/plans", json={"ids": [entry_id]}).json()["skipped"]["duplicate"] == 1
    result = client.post("/api/discovery/search", json={}).json()
    assert result["items"][0]["state"] == "imported"


@pytest.mark.parametrize("mode", ["hash", "oversize", "short", "redirect", "unavailable"])
def test_bad_downloads_do_not_import(acquisition, monkeypatch, mode):
    client, service = acquisition
    payload = b"synthetic game"
    task_id = queue(client, add_entry(service, payload))
    content = (
        b"x" * len(payload)
        if mode == "hash"
        else payload + b"x"
        if mode == "oversize"
        else payload[:-1]
        if mode == "short"
        else payload
    )
    code = 302 if mode == "redirect" else 404 if mode == "unavailable" else 200
    network(service, monkeypatch, lambda request: httpx.Response(code, content=content))
    result = run_task(service, task_id)
    assert result.status == ("retry_wait" if mode == "short" else "failed")
    assert client.get("/api/games").json()["total"] == 0
    if mode != "short":
        assert not (service.manager.directory(task_id) / "download.part").exists()


def test_retry_after_backoff_then_success(acquisition, monkeypatch):
    client, service = acquisition
    payload = b"retry fixture"
    task_id = queue(client, add_entry(service, payload))
    network(service, monkeypatch, lambda request: httpx.Response(429, headers={"Retry-After": "17"}))
    before = time.time()
    failed = run_task(service, task_id)
    assert failed.status == "retry_wait"
    assert failed.retry_at >= before + 17
    network(service, monkeypatch, lambda request: httpx.Response(200, content=payload))
    assert run_task(service, task_id).status == "imported"


@pytest.mark.parametrize("supports_range", [True, False])
def test_pause_resume_with_range_or_restart(acquisition, monkeypatch, supports_range):
    client, service = acquisition
    payload = b"a" * 65536 + b"b" * 65536 + b"c" * 65536
    task_id = queue(client, add_entry(service, payload))
    original = service.manager.checkpoint

    def pause_at_chunk(task_id, received=None, **updates):
        if received == 65536:
            service.manager.control(task_id, "pause")
        return original(task_id, received, **updates)

    monkeypatch.setattr(service.manager, "checkpoint", pause_at_chunk)

    class Chunks(httpx.SyncByteStream):
        def __iter__(self):
            for offset in range(0, len(payload), 65536):
                yield payload[offset : offset + 65536]

    network(service, monkeypatch, lambda request: httpx.Response(200, stream=Chunks()))
    assert run_task(service, task_id).status == "paused"
    partial = service.manager.directory(task_id) / "download.part"
    assert partial.stat().st_size == 65536
    monkeypatch.setattr(service.manager, "checkpoint", original)

    def resumed(request):
        assert request.headers["range"] == "bytes=65536-"
        if supports_range:
            return httpx.Response(
                206,
                headers={"Content-Range": f"bytes 65536-{len(payload) - 1}/{len(payload)}"},
                content=payload[65536:],
            )
        return httpx.Response(200, content=payload)

    network(service, monkeypatch, resumed)
    service.manager.control(task_id, "resume")
    assert run_task(service, task_id).status == "imported"


def test_cancel_and_retry_cleanup(acquisition):
    client, service = acquisition
    task_id = queue(client, add_entry(service))
    folder = service.manager.directory(task_id)
    folder.mkdir(parents=True)
    (folder / "download.part").write_bytes(b"partial")
    assert client.post(f"/api/downloads/{task_id}/control", json={"action": "cancel"}).status_code == 200
    assert not folder.exists()
    assert client.post(f"/api/downloads/{task_id}/control", json={"action": "retry"}).status_code == 200
    assert client.get("/api/downloads").json()["items"][0]["status"] == "queued"


def test_capacity_budget_filters_and_stale_plans(acquisition):
    client, service = acquisition
    first = add_entry(service, b"1", "alpha", size=60_000_000)
    add_entry(service, b"2", "beta", license=None, downloadable=False)
    config = client.get("/api/acquisition/settings").json()
    config.update(
        target_bytes=1_000_000_000,
        reserved_bytes=900_000_000,
        automatic_max_bytes=10,
        automatic_filters={"platforms": ["gb"], "sources": ["test"], "licenses": ["CC0-1.0"]},
    )
    assert client.put("/api/acquisition/settings", json=config).status_code == 200
    manual = client.post("/api/acquisition/plans", json={"ids": [first]}).json()
    assert not manual["can_confirm"]
    assert manual["storage"]["usable_bytes"] == 50_000_000
    assert (
        client.post(f"/api/acquisition/plans/{manual['id']}/confirm", json={"confirmed": True}).status_code
        == 400
    )
    auto = client.post("/api/acquisition/plans", json={"mode": "automatic"}).json()
    assert auto["skipped"]["budget"] == 1
    assert auto["count"] == 0
    assert client.post("/api/discovery/search", json={"licenses": ["CC0-1.0"]}).json()["total"] == 1
    config.update(target_bytes=128_000_000_000, reserved_bytes=8_000_000_000)
    client.put("/api/acquisition/settings", json=config)
    plan = client.post("/api/acquisition/plans", json={"all_filtered": True}).json()
    assert plan["count"] == 1
    assert plan["skipped"]["unsupported"] == 1
    with service.sessions.begin() as db:
        db.get(DiscoveryEntry, first).downloadable = False
    assert (
        client.post(f"/api/acquisition/plans/{plan['id']}/confirm", json={"confirmed": True}).status_code
        == 400
    )


def test_concurrency_limit(acquisition, monkeypatch):
    client, service = acquisition
    payload = b"shared fixture"
    ids = [add_entry(service, payload, f"game-{i}") for i in range(3)]
    # Configure duplicate inclusion to exercise concurrent post-download deduplication.
    config = client.get("/api/acquisition/settings").json()
    config.update(concurrency=2, exclude_duplicates=False)
    client.put("/api/acquisition/settings", json=config)
    tasks = [queue(client, entry_id) for entry_id in ids]
    gate = threading.Event()

    def handler(request):
        assert gate.wait(5)
        return httpx.Response(200, content=payload)

    network(service, monkeypatch, handler)
    try:
        service.manager.tick()
        assert len(service.manager.active) == 2
        states = client.get("/api/downloads").json()["counts"]
        assert states["running"] == 2 and states["queued"] == 1
    finally:
        gate.set()
    for future in service.manager.active.values():
        future.result(timeout=10)
    service.manager.tick()
    for future in service.manager.active.values():
        future.result(timeout=10)
    assert client.get("/api/games").json()["total"] == 1
    with service.sessions() as db:
        assert all(db.get(DownloadTask, task).status == "imported" for task in tasks)


def test_queue_survives_restart(acquisition):
    client, service = acquisition
    task_id = queue(client, add_entry(service))
    with service.sessions.begin() as db:
        db.get(DownloadTask, task_id).status = "running"
    # Recover the same database through the production startup path.
    with TestClient(create_app(service.data_dir)) as restored:
        task = restored.get("/api/downloads").json()["items"][0]
        assert task["id"] == task_id
        assert task["status"] == "paused"


@pytest.mark.parametrize("name", ["../bad.gb", "/bad.gb", "C:/bad.gb", "folder/../../bad.gb"])
def test_archive_traversal(tmp_path, name):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(name, b"fixture")
    with pytest.raises(ValueError):
        validate_archive(archive)
    assert not (tmp_path / "bad.gb").exists()


def test_archive_bomb_and_crc(tmp_path):
    path = tmp_path / "bomb.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("demo.gb", b"\0" * 2_000_000)
    with pytest.raises(ValueError):
        validate_archive(path)


@pytest.mark.parametrize(
    "license_name,disabled,downloadable",
    [("MIT", False, True), (None, False, False), ("freeware", False, False), ("MIT", True, False)],
)
def test_provider_authorization_and_missing_metadata(license_name, disabled, downloadable):
    raw = {
        "slug": "demo",
        "title": "Demo",
        "typetag": "game",
        "platform": "GB",
        "gameLicense": license_name,
        "files": [{"filename": "demo.gb", "default": True}],
        "use-requirements": {"disable-downloads": disabled},
    }
    entry = parse_entry(
        "gbdev",
        "a" * 40,
        "entries/demo/game.json",
        raw,
        {"entries/demo/demo.gb": {"sha": "b" * 40, "size": 100}},
    )
    assert entry["downloadable"] is downloadable
    assert entry["author"] is None and entry["year"] is None and entry["genre"] is None
    assert entry["payload"]["cover"] is None
    assert entry["payload"]["evidence"]["declaration"] == raw


def test_metadata_cache_and_git_hash(tmp_path):
    raw = {
        "slug": "demo",
        "title": "Demo",
        "typetag": "game",
        "platform": "GB",
        "license": "MIT",
        "files": [{"filename": "demo.gb"}],
    }
    content = json.dumps(raw).encode()
    sha = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
    tree = {
        "sha": "c" * 40,
        "tree": [
            {"path": "entries/demo/game.json", "type": "blob", "sha": sha},
            {"path": "entries/demo/demo.gb", "type": "blob", "sha": "b" * 40, "size": 100},
        ],
    }
    calls = []

    class FakeHTTP:
        def read(self, url, limit):
            calls.append(url)
            return json.dumps(tree).encode() if "api.github.com" in url else content

    catalog = GitHubCatalog(FakeHTTP(), tmp_path)
    assert len(catalog.load("gbdev")) == 1
    assert len(catalog.load("gbdev")) == 1
    assert sum("raw.githubusercontent" in url for url in calls) == 1
    assert not any(url.endswith(".gb") for url in calls)


def test_enrichment_exact_hash_ambiguity_and_cover_cache(acquisition, monkeypatch):
    client, service = acquisition
    payload = b"metadata fixture"
    entry_id = add_entry(service, payload)
    task_id = queue(client, entry_id)
    network(service, monkeypatch, lambda request: httpx.Response(200, content=payload))
    task = run_task(service, task_id)
    with service.sessions.begin() as db:
        game = db.get(Game, task.game_id)
        game.title = "My manual title"
        game.author = ""
        game.year = None
        game.genre = "My genre"
    response = client.post("/api/metadata/enrich", json={"apply": True, "covers": False})
    assert response.status_code == 202
    job_id = response.json()["id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed"}:
            break
        time.sleep(0.01)
    assert job["status"] == "completed", job
    result = job["result"]
    assert result["matches"][0]["changes"]["author"] == "Fixture author"
    current = client.get(f"/api/games/{task.game_id}").json()
    assert current["genre"] == "My genre" and current["title"] == "My manual title"
    add_entry(service, payload, "ambiguous")
    assert service.enrich(EnrichInput())["unresolved"][0]["reason"] == "Corrispondenza ambigua"
    image = io.BytesIO()
    Image.new("RGB", (2, 2), (20, 30, 40)).save(image, format="PNG")
    data = image.getvalue()
    with service.sessions() as db:
        entry = db.get(DiscoveryEntry, entry_id)
        entry.payload = {
            "cover": {
                "url": "https://example.org/cover.png",
                "license": "CC0-1.0",
                "git_blob_sha1": hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest(),
            }
        }
    calls = []
    monkeypatch.setattr(service.http, "read", lambda *args: calls.append(args) or data)
    first = service.cache_cover(entry)
    assert first == service.cache_cover(entry) and len(calls) == 1


def test_robots_denial_and_private_network(monkeypatch):
    http = PublicHTTP(
        httpx.MockTransport(lambda request: httpx.Response(200, text="User-agent: *\nDisallow: /blocked\n"))
    )
    monkeypatch.setattr("backend.network.validate_url", lambda url: None)
    with pytest.raises(ValueError, match="robots"):
        http.read("https://example.org/blocked/file")
    http.close()
