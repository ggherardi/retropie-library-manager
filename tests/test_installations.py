import hashlib
import time
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from remote_fixture import FakeConnection
from test_intelligence import archive, component, import_rows

from backend.content_checks import disc_check, format_check
from backend.identification import Identifier
from backend.installation_preflight import preflight
from backend.main import create_app
from backend.remote_fs import SafeRemote


def nes(path, seed=1):
    header = b"NES\x1a\x01\x00" + bytes(10)
    path.write_bytes(header + bytes([seed]) * 16384)
    return path


def disc(folder, name="Synthetic (Disc 1)"):
    data = bytearray(2352 * 40)
    offset = 16 * 2352 + 24
    data[offset : offset + 7] = b"\x01CD001\x01"
    data[offset + 8 : offset + 19] = b"PLAYSTATION"
    data[offset + 80 : offset + 84] = (40).to_bytes(4, "little")
    data[offset + 84 : offset + 88] = (40).to_bytes(4, "big")
    (folder / (name + ".bin")).write_bytes(data)
    cue = folder / (name + ".cue")
    cue.write_text(f'FILE "{name}.bin" BINARY\n TRACK 01 MODE2/2352\n INDEX 01 00:00:00\n')
    return cue


def wait(client, batch_id, predicate, timeout=25):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        result = client.get("/api/installations/" + batch_id).json()
        if predicate(result):
            return result
        time.sleep(0.025)
    raise AssertionError(result)


@pytest.fixture
def setup(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    remote = FakeConnection(tmp_path / "remote")
    app = create_app(tmp_path / "data")
    app.state.devices.connect = lambda config: remote
    app.state.installations.preflight = lambda *args: {"core": "synthetic", "installed": True}
    with TestClient(app, headers={"X-RLM-Request": "1"}) as client:
        client.put("/api/settings", json={"import_roots": [str(source)], "export_root": str(source)})
        device = client.post(
            "/api/devices", json={"name": "Synthetic", "host": "test-pi.invalid", "is_default": True}
        ).json()["id"]
        yield app, client, source, remote, device


def create(client, paths, mode="install", recursive=True, key=None):
    response = client.post(
        "/api/installations/local",
        json={
            "paths": [str(p) for p in paths],
            "mode": mode,
            "recursive": recursive,
            "request_key": key or str(uuid4()),
        },
    )
    assert response.status_code == 202, response.text
    batch_id = response.json()["id"]
    return wait(client, batch_id, lambda b: b["status"] in {"preview", "failed"})


def confirm(client, batch):
    response = client.post(
        f"/api/installations/{batch['id']}/confirm",
        json={"confirmed": True, "rights_confirmed": True, "enrich": True},
    )
    assert response.status_code == 200, response.text


def finished(client, batch):
    return wait(client, batch["id"], lambda b: b["status"] in {"completed", "completed_with_errors"})


def test_single_automatic_install_duplicate_and_repeat_zero_writes(setup):
    app, client, source, remote, _ = setup
    path = nes(source / "Original readable.nes")
    original = path.read_bytes()
    batch = create(client, [path])
    assert batch["counts"] == {"ready": 1}
    assert client.get("/api/stats").json()["games"] == 0
    confirm(client, batch)
    result = finished(client, batch)
    item = result["items"][0]
    assert item["status"] == "installed" and item["installed"] and item["pc_present"]
    assert not item["launched"] and item["visibility"] == "awaiting_local_check"
    assert item["progress"]["report"]["transferred_bytes"] > len(original)
    before = remote.sftp.writes
    batch = create(client, [path])
    assert batch["items"][0]["identification"]["duplicate"]
    confirm(client, batch)
    result = finished(client, batch)
    assert result["items"][0]["progress"]["report"]["transferred_bytes"] == 0
    assert remote.sftp.writes == before
    assert path.read_bytes() == original
    assert client.get("/api/stats").json()["games"] == 1


def test_massive_local_documents_bios_and_ambiguity_independent(setup):
    _, client, source, remote, _ = setup
    for n in range(12):
        nes(source / f"Game {n}.nes", n)
    (source / "README.md").write_text("# This is a document, not a Mega Drive ROM")
    (source / "REFERENCE.md").write_text("reference")
    (source / "scph1001.bin").write_bytes(b"not a real BIOS")
    (source / "uncertain.bin").write_bytes(b"raw ambiguous data")
    batch = create(client, [source], mode="local")
    assert batch["counts"] == {"ready": 12, "ignored": 3, "awaiting_decision": 1}
    confirm(client, batch)
    result = wait(client, batch["id"], lambda b: b["counts"].get("imported_local") == 12)
    assert result["counts"]["awaiting_decision"] == 1 and remote.sftp.writes == 0
    unknown = next(i for i in result["items"] if i["status"] == "awaiting_decision")
    client.post(
        f"/api/installations/items/{unknown['id']}/decision", json={"action": "choose", "platform": "psx"}
    )
    assert client.get(f"/api/installations/{batch['id']}").json()["counts"]["awaiting_decision"] == 1
    client.post(f"/api/installations/items/{unknown['id']}/decision", json={"action": "skip"})
    finished(client, batch)


def test_recursive_opt_out_and_no_arbitrary_paths(setup, tmp_path):
    _, client, source, _, _ = setup
    nes(source / "Top.nes")
    sub = source / "sub"
    sub.mkdir()
    nes(sub / "Nested.nes", 2)
    assert create(client, [source], mode="local", recursive=False)["total"] == 1
    response = client.post(
        "/api/installations/local",
        json={"paths": [str(tmp_path)], "mode": "local", "request_key": str(uuid4())},
    )
    assert response.status_code == 400


def test_changed_file_hash_never_imported(setup):
    _, client, source, _, _ = setup
    path = nes(source / "Changed.nes")
    batch = create(client, [path])
    nes(path, 2)
    confirm(client, batch)
    result = finished(client, batch)
    assert result["counts"] == {"failed": 1}
    assert "cambiato" in result["items"][0]["error"]["cause"]
    assert client.get("/api/stats").json()["games"] == 0


def test_ps1_cue_and_multidisc_grouping(setup):
    _, client, source, _, _ = setup
    one = disc(source)
    two = disc(source, "Synthetic (Disc 2)")
    batch = create(client, [source], mode="local")
    assert batch["counts"] == {"ready": 1}
    assert len(batch["items"][0]["candidate"]["files"]) == 4
    confirm(client, batch)
    assert finished(client, batch)["counts"] == {"imported_local": 1}
    playlist = source / "Synthetic.m3u"
    playlist.write_text(one.name + "\n" + two.name + "\n")
    second = create(client, [source], mode="local")
    assert second["counts"] == {"ready": 1}
    assert len(second["items"][0]["candidate"]["files"]) == 5


@pytest.mark.parametrize("damage", ["missing", "truncated", "index", "traversal", "iso"])
def test_ps1_rejects_incomplete_or_foreign_discs(tmp_path, damage):
    cue = disc(tmp_path)
    track = cue.with_suffix(".bin")
    if damage == "missing":
        track.unlink()
    if damage == "truncated":
        track.write_bytes(track.read_bytes()[:-1])
    if damage == "index":
        cue.write_text(cue.read_text().replace("00:00:00", "99:00:00"))
    if damage == "traversal":
        cue.write_text(cue.read_text().replace('FILE "', 'FILE "../'))
    if damage == "iso":
        track.write_bytes(bytes(track.stat().st_size))
    with pytest.raises((ValueError, OSError)):
        disc_check(cue, tmp_path)


def test_arcade_content_match_renamed_archive_and_missing_dependency(setup):
    app, client, source, _, _ = setup
    payload = b"synthetic arcade program"
    rows = [
        {
            "name": "technical",
            "title": "Verified readable title",
            "components": [component("program.bin", payload)],
        }
    ]
    import_rows(client, source, rows)
    path = archive(source, "totally-renamed", {"program.bin": payload})
    found = Identifier(app.state.sessions).identify(path, source, [str(source)], [path])
    assert found["status"] == "ready" and found["identification"]["title"] == "Verified readable title"
    rows[0]["components"].append(component("missing.bin", b"absent"))
    import_rows(client, source, rows)
    result = create(client, [path], mode="local")
    assert result["counts"] == {"awaiting_decision": 1}
    candidates = result["items"][0]["identification"]["candidates"]
    assert candidates[0]["report"]["problems"][0]["file"] == "missing.bin"


def test_neogeo_bios_dependency_report(setup):
    app, client, source, _, _ = setup
    rows = [
        {"name": "neogeo", "kind": "bios", "components": [component("bios.bin", b"firmware fixture")]},
        {
            "name": "demo",
            "title": "Neo Geo synthetic",
            "romof": "neogeo",
            "components": [component("game.bin", b"game fixture")],
        },
    ]
    import_rows(client, source, rows)
    path = archive(source, "demo", {"game.bin": b"game fixture"})
    found = Identifier(app.state.sessions).archive(path, [str(source)], lambda: None)
    assert not found["chosen"]
    assert any(p["set"] == "neogeo" for p in found["candidates"][0]["report"]["problems"])


def test_offline_keeps_local_then_resumes(setup):
    app, client, source, remote, _ = setup

    def offline(config):
        raise OSError("connection offline")

    app.state.devices.connect = offline
    batch = create(client, [nes(source / "Offline.nes")])
    confirm(client, batch)
    result = wait(client, batch["id"], lambda b: b["counts"].get("waiting_device") == 1)
    assert result["items"][0]["pc_present"] and not result["items"][0]["installed"]
    app.state.devices.connect = lambda config: remote
    app.state.installations.offline_until.clear()
    client.post(f"/api/installations/{batch['id']}/control", json={"action": "retry"})
    assert finished(client, batch)["counts"] == {"installed": 1}


def test_failed_media_does_not_block_installation(setup, monkeypatch):
    app, client, source, _, _ = setup

    def unavailable(*args):
        raise OSError("Image source unavailable")

    monkeypatch.setattr(app.state.media, "preview", unavailable)
    batch = create(client, [nes(source / "No image.nes")])
    confirm(client, batch)
    item = finished(client, batch)["items"][0]
    assert item["status"] == "installed" and any("Image source" in w for w in item["warnings"])


def test_es_open_persistent_metadata_queue_and_recovery(setup):
    app, client, source, remote, _ = setup
    remote.running = True
    batch = create(client, [nes(source / "Pending.nes")])
    confirm(client, batch)
    result = wait(client, batch["id"], lambda b: b["counts"].get("pending_refresh") == 1)
    assert result["items"][0]["installed"] and not result["items"][0]["launched"]
    assert not list(remote.sftp.root.rglob("gamelist.xml"))
    app.state.installations.shutdown()
    remote.running = False
    app.state.installations.stop.clear()
    app.state.installations.start()
    result = finished(client, batch)
    assert result["items"][0]["progress"]["report"]["skipped_files"] == 1
    assert list(remote.sftp.root.rglob("gamelist.xml"))


def test_transfer_interrupted_retries_verified_partial(setup, monkeypatch):
    _, client, source, _, _ = setup
    original = SafeRemote.upload
    attempts = []

    def interrupted(self, path, stream, size, expected, checkpoint):
        attempts.append(path)
        if len(attempts) == 1:
            self.mkdir(str(Path(path).parent).replace("\\", "/"))
            with self.sftp.open(path, "wb") as target:
                target.write(stream.read(100))
            raise OSError("connection interrupted")
        return original(self, path, stream, size, expected, checkpoint)

    monkeypatch.setattr(SafeRemote, "upload", interrupted)
    batch = create(client, [nes(source / "Interrupted.nes")])
    confirm(client, batch)
    assert finished(client, batch)["counts"] == {"installed": 1}
    assert attempts[0] == attempts[1]


def test_remote_conflict_preserves_rom_and_saves(setup):
    _, client, source, remote, _ = setup
    path = nes(source / "Conflict.nes")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    folder = remote.sftp.resolve("/home/pi/RetroPie/roms/nes/rlm-" + sha[:24])
    folder.mkdir()
    (folder / path.name).write_bytes(b"existing remote content")
    save = folder / "user.srm"
    save.write_bytes(b"user save")
    batch = create(client, [path])
    confirm(client, batch)
    result = finished(client, batch)
    assert result["counts"] == {"failed": 1} and not result["items"][0]["installed"]
    assert (
        folder / path.name
    ).read_bytes() == b"existing remote content" and save.read_bytes() == b"user save"


def test_pause_cancel_and_idempotent_confirmation(setup):
    _, client, source, remote, _ = setup
    path = nes(source / "Paused.nes")
    key = str(uuid4())
    batch = create(client, [path], key=key)
    assert create(client, [path], key=key)["id"] == batch["id"]
    client.post(f"/api/installations/{batch['id']}/control", json={"action": "pause"})
    confirm(client, batch)
    time.sleep(0.6)
    assert remote.sftp.writes == 0
    client.post(f"/api/installations/{batch['id']}/control", json={"action": "resume"})
    confirm(client, batch)
    assert finished(client, batch)["total"] == 1
    cancelled = create(client, [nes(source / "Cancelled.nes", 5)])
    client.post(f"/api/installations/{cancelled['id']}/control", json={"action": "cancel"})
    assert client.get(f"/api/installations/{cancelled['id']}").json()["counts"] == {"cancelled": 1}


def test_chunk_upload_integrity_idempotence_and_resume(setup):
    _, client, source, _, _ = setup
    data = nes(source / "Upload.nes").read_bytes()
    batch = client.post(
        "/api/installations/uploads",
        json={
            "files": [{"relative": "folder/Upload.nes", "size": len(data)}],
            "mode": "local",
            "request_key": str(uuid4()),
        },
    ).json()
    target = batch["uploads"][0]
    url = f"/api/installations/{batch['id']}/uploads/{target['id']}"
    for offset, block in [(0, data[:500]), (0, data[:500]), (500, data[500:])]:
        response = client.put(
            url + f"?offset={offset}",
            content=block,
            headers={"X-Chunk-SHA256": hashlib.sha256(block).hexdigest()},
        )
        assert response.status_code == 200, response.text
    response = client.put(
        url + "?offset=0",
        content=b"changed",
        headers={"X-Chunk-SHA256": hashlib.sha256(b"changed").hexdigest()},
    )
    assert response.status_code == 400
    assert client.post(f"/api/installations/{batch['id']}/analyze").status_code == 202
    batch = wait(client, batch["id"], lambda b: b["status"] == "preview")
    confirm(client, batch)
    assert finished(client, batch)["counts"] == {"imported_local": 1}


@pytest.mark.parametrize(
    "relative",
    ["../outside.nes", "C:/game.nes", "sub/CON.bin", "/root.nes", "sub/file:ads.nes", "bad. /x.nes"],
)
def test_upload_path_traversal_rejected(setup, relative):
    _, client, _, _, _ = setup
    response = client.post(
        "/api/installations/uploads",
        json={"files": [{"relative": relative, "size": 1}], "mode": "local", "request_key": str(uuid4())},
    )
    assert response.status_code == 400


def test_psx_bios_preflight_requires_verified_hash():
    class Connection:
        def execute(self, _):
            return '{"installed":true,"core":"lr-pcsx-rearmed","bios":[{"verified":false}]}'

    with pytest.raises(ValueError, match="BIOS PS1"):
        preflight(Connection(), {}, "psx")


def test_nes_corruption_is_not_hidden_by_extension(tmp_path):
    path = tmp_path / "bad.nes"
    path.write_bytes(b"NES\x1a\x10\x00" + bytes(10))
    with pytest.raises(ValueError, match="troncata"):
        format_check(path)


def test_mass_install_serializes_gamelist_plans(setup):
    from defusedxml import ElementTree

    _, client, source, remote, _ = setup
    paths = [nes(source / f"Batch {n}.nes", n + 20) for n in range(5)]
    batch = create(client, paths)
    confirm(client, batch)
    result = finished(client, batch)
    assert result["counts"] == {"installed": 5}, result
    xml = next(remote.sftp.root.rglob("gamelist.xml"))
    assert len(ElementTree.parse(xml).findall("game")) == 5


def test_restart_new_app_restores_authorized_queue(tmp_path):
    from backend.db import InstallationBatch, InstallationItem

    source = tmp_path / "source"
    source.mkdir()
    path = nes(source / "Crash recovery.nes")
    data = tmp_path / "data"
    remote = FakeConnection(tmp_path / "remote")
    first = create_app(data)
    with TestClient(first, headers={"X-RLM-Request": "1"}) as client:
        first.state.installations.shutdown()
        client.put("/api/settings", json={"import_roots": [str(source)], "export_root": str(source)})
        device = client.post("/api/devices", json={"name": "Recovery", "host": "test-pi.invalid"}).json()[
            "id"
        ]
        identified = Identifier(first.state.sessions).identify(path, source, [str(source)], [path])
        identified.pop("consumed")
        batch_id = str(uuid4())
        with first.state.sessions.begin() as db:
            db.add(
                InstallationBatch(
                    id=batch_id,
                    request_key=str(uuid4()),
                    device_id=device,
                    mode="install",
                    status="running",
                    authorized=True,
                    request={"input": {"paths": [str(path)], "recursive": True}, "options": {"enrich": True}},
                )
            )
            db.add(InstallationItem(id=str(uuid4()), batch_id=batch_id, source_key=str(path), **identified))
    second = create_app(data)
    second.state.devices.connect = lambda config: remote
    second.state.installations.preflight = lambda *args: {"core": "synthetic", "installed": True}
    with TestClient(second, headers={"X-RLM-Request": "1"}) as client:
        result = finished(client, {"id": batch_id})
        assert result["counts"] == {"installed": 1}
        assert client.get("/api/stats").json()["games"] == 1


def test_pause_during_transfer_resumes_same_staging(setup, monkeypatch):
    from backend.db import SyncRun

    app, client, source, remote, _ = setup
    original = SafeRemote.upload
    attempts = []
    batch = create(client, [nes(source / "Pause transfer.nes")])

    def pausing(self, path, stream, size, expected, checkpoint):
        attempts.append(path)
        if len(attempts) == 1:
            self.mkdir(str(Path(path).parent).replace("\\", "/"))
            with self.sftp.open(path, "wb") as target:
                target.write(stream.read(100))
            app.state.installations.control(batch["id"], "pause")
        return original(self, path, stream, size, expected, checkpoint)

    monkeypatch.setattr(SafeRemote, "upload", pausing)
    confirm(client, batch)
    paused = wait(client, batch["id"], lambda b: b["control"] == "pause" and b["counts"].get("paused") == 1)
    run_id = paused["items"][0]["sync_run_id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with app.state.sessions() as db:
            if db.get(SyncRun, run_id).status == "paused":
                break
        time.sleep(0.02)
    assert any(remote.sftp.root.rglob(".rlm-stage-*"))
    client.post(f"/api/installations/{batch['id']}/control", json={"action": "resume"})
    result = finished(client, batch)
    assert result["counts"] == {"installed": 1}
    assert result["items"][0]["sync_run_id"] == run_id and attempts[0] == attempts[1]


def test_disk_reserve_blocks_without_remote_writes(setup):
    _, client, source, remote, _ = setup
    remote.free = 100 * 1024**2
    batch = create(client, [nes(source / "Reserve.nes")])
    confirm(client, batch)
    result = finished(client, batch)
    assert result["counts"] == {"failed": 1}
    assert "Spazio" in result["items"][0]["error"]["cause"] and remote.sftp.writes == 0


def test_offline_without_local_consent_keeps_queue_only(setup):
    app, client, source, _, _ = setup

    def offline(config):
        raise OSError("connection offline")

    app.state.devices.connect = offline
    batch = create(client, [nes(source / "Wait for device.nes")])
    client.post(
        f"/api/installations/{batch['id']}/confirm",
        json={"confirmed": True, "rights_confirmed": True, "keep_local_when_offline": False},
    )
    result = wait(client, batch["id"], lambda b: b["counts"].get("waiting_device") == 1)
    assert not result["items"][0]["pc_present"] and client.get("/api/stats").json()["games"] == 0


def test_browser_upload_recovers_rename_before_receipt_commit(setup):
    app, client, source, _, _ = setup
    from backend.db import InstallationUpload

    data = nes(source / "Recover.nes").read_bytes()
    batch = client.post(
        "/api/installations/uploads",
        json={
            "files": [{"relative": "Recover.nes", "size": len(data)}],
            "mode": "local",
            "request_key": str(uuid4()),
        },
    ).json()
    upload = batch["uploads"][0]
    url = f"/api/installations/{batch['id']}/uploads/{upload['id']}?offset=0"
    headers = {"X-Chunk-SHA256": hashlib.sha256(data).hexdigest()}
    assert client.put(url, content=data, headers=headers).status_code == 200
    with app.state.sessions.begin() as db:
        row = db.get(InstallationUpload, upload["id"])
        row.received, row.sha256, row.chunks, row.status = 0, "", {}, "waiting"
    response = client.put(url, content=data, headers=headers)
    assert response.status_code == 200 and response.json()["status"] == "complete"


def test_ps1_playlist_same_discs_is_logical_duplicate(setup):
    _, client, source, _, _ = setup
    cue = disc(source, "Logical")
    original = create(client, [cue], mode="local")
    confirm(client, original)
    finished(client, original)
    playlist = source / "Logical.m3u"
    playlist.write_text(cue.name + "\n")
    batch = create(client, [playlist], mode="local")
    assert batch["items"][0]["identification"]["duplicate"]
    confirm(client, batch)
    finished(client, batch)
    assert client.get("/api/stats").json()["games"] == 1


def test_shared_bios_does_not_identify_unrelated_games(setup):
    app, client, source, _, _ = setup
    bios = component("common.bin", b"shared firmware fixture")
    rows = [
        {"name": "board", "kind": "bios", "components": [bios]},
        {"name": "correct", "components": [component("game.bin", b"selected program"), bios]},
        {"name": "unrelated", "components": [component("other.bin", b"different program"), bios]},
    ]
    import_rows(client, source, rows)
    path = archive(
        source, "renamed", {"game.bin": b"selected program", "common.bin": b"shared firmware fixture"}
    )
    found = Identifier(app.state.sessions).archive(path, [str(source)], lambda: None)
    assert [c["title"] for c in found["candidates"]] == ["correct"]
    assert found["chosen"]["matched_components"] == 1


def test_technical_title_requires_verified_operator_decision(setup):
    _, client, source, _, _ = setup
    batch = create(client, [nes(source / "RLM-ABCDEF.nes")], mode="local")
    assert batch["counts"] == {"awaiting_decision": 1}
    item_id = batch["items"][0]["id"]
    response = client.post(
        f"/api/installations/items/{item_id}/decision",
        json={"action": "choose", "title": "Verified fixture title", "confirmed_title": True},
    )
    assert response.status_code == 200
    confirm(client, batch)
    result = finished(client, batch)
    assert result["items"][0]["title"] == "Verified fixture title"


def test_resuming_enriched_local_item_never_syncs(setup):
    from backend.db import InstallationItem

    app, client, source, remote, _ = setup
    batch = create(client, [nes(source / "Only PC.nes")], mode="local")
    confirm(client, batch)
    result = finished(client, batch)
    with app.state.sessions.begin() as db:
        item = db.get(InstallationItem, result["items"][0]["id"])
        item.status = "paused"
    client.post(f"/api/installations/{batch['id']}/control", json={"action": "resume"})
    assert finished(client, batch)["counts"] == {"imported_local": 1}
    assert remote.sftp.writes == 0
