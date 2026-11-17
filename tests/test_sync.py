import base64
import hashlib
import io
import time
from pathlib import Path
from xml.etree.ElementTree import ParseError

import paramiko
import pytest
from defusedxml.common import DefusedXmlException
from fastapi.testclient import TestClient
from remote_fixture import FakeConnection

from backend.db import Game, SyncRun
from backend.gamelist import merge_gamelist, parse_xml
from backend.main import create_app
from backend.remote_fs import SafeRemote
from backend.scanner import candidate
from backend.ssh_connection import SSHConnection
from backend.sync_engine import SyncCancelled, build_plan, perform_sync
from backend.sync_schemas import DeviceInput, SyncInput


@pytest.fixture
def remote(tmp_path):
    return FakeConnection(tmp_path / "remote")


def config():
    return {
        **DeviceInput(name="Test Pi", host="retropie").model_dump(exclude={"is_default"}),
        "fingerprint": "test",
    }


def game_at(tmp_path, multidisc=False):
    folder = tmp_path / "local"
    folder.mkdir(exist_ok=True)
    if multidisc:
        entries = []
        for n in (1, 2):
            track = folder / f"Gioco è & (Disc {n}).bin"
            track.write_bytes(bytes([n]) * 70000)
            cue = folder / f"Gioco è & (Disc {n}).cue"
            cue.write_text(f'FILE "{track.name}" BINARY\n TRACK 01 MODE2/2352\n', encoding="utf-8")
            entries.append(cue)
        item = candidate(entries, folder, "psx")
    else:
        path = folder / "Title & ü.gb"
        path.write_bytes(b"synthetic authorized fixture" * 5000)
        item = candidate([path], folder, "gb")
    item.pop("entrypoints")
    return Game(
        id=1,
        **item,
        license="CC0-1.0",
        provenance="Synthetic test",
        author="Author",
        publisher="Publisher",
        description="A & B <C>",
        year=2024,
        genre="Puzzle",
        favorite=True,
        cover_path="",
    )


def options(game, **kwargs):
    return SyncInput(device_id="device", game_ids=[game.id], **kwargs)


def test_dry_run_incremental_and_metadata(tmp_path, remote):
    game = game_at(tmp_path)
    plan = build_plan(remote, config(), [game], options(game))
    assert plan["can_sync"] and remote.sftp.writes == 0
    result = perform_sync(remote, plan, "first", lambda p: None)
    assert result["transferred_bytes"] >= game.size
    xml = remote.sftp.resolve(plan["gamelists"][0]["path"]).read_bytes()
    root = parse_xml(xml)
    assert root.findtext("game/name") == game.title
    assert root.findtext("game/desc") == "A & B <C>"
    assert root.findtext("game/publisher") == "Publisher"
    second = build_plan(remote, config(), [game], options(game))
    assert second["required_bytes"] == 0
    writes = remote.sftp.writes
    repeated = perform_sync(remote, second, "second", lambda p: None)
    assert repeated["transferred_bytes"] == 0 and remote.sftp.writes == writes


def test_gamelist_preserves_unknown_metadata_and_comments():
    original = b'<gameList><!--keep--><game id="9"><path>./demo.gb</path><name>Old</name><rating>0.8</rating><playcount>9</playcount><custom>keep</custom></game><folder><path>./other</path></folder></gameList>'
    game = {"launch": "demo.gb", "title": "New & <name>", "favorite": True, "description": None}
    merged = merge_gamelist(original, [game], "/roms/gb")
    root = parse_xml(merged)
    assert root.findtext("game/name") == "New & <name>"
    assert root.findtext("game/custom") == "keep" and root.findtext("game/playcount") == "9"
    assert b"<!--keep-->" in merged and root.find("folder") is not None
    assert root.find("game").attrib["id"] == "9"
    assert merge_gamelist(merged, [game], "/roms/gb") == merged


def test_repair_existing_library_changes_only_metadata_and_is_repeatable(tmp_path, remote):
    game = game_at(tmp_path)
    first = build_plan(remote, config(), [game], options(game))
    perform_sync(remote, first, "original", lambda p: None)
    xml_path = remote.sftp.resolve(first["gamelists"][0]["path"])
    root = parse_xml(xml_path.read_bytes())
    for folder in root.findall("folder"):
        root.remove(folder)  # Legacy generator wrote game entries, but no folder titles.
    from xml.etree.ElementTree import SubElement, tostring

    SubElement(root.find("game"), "playcount").text = "12"
    original = tostring(root, encoding="utf-8", xml_declaration=True)
    xml_path.write_bytes(original)
    rom_path = remote.sftp.resolve(first["groups"][0]["files"][0]["path"])
    save = rom_path.with_suffix(".srm")
    save.write_bytes(b"existing battery save")
    state = rom_path.with_suffix(".state")
    state.write_bytes(b"existing save state")
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (rom_path, save, state)}

    plan = build_plan(remote, config(), [game], options(game))
    assert plan["can_sync"] and plan["title_reviews"] == []
    assert plan["groups"][0]["counts"] == {"new": 0, "present": 1, "modified": 0}
    assert plan["gamelists"][0]["state"] == "update"
    result = perform_sync(remote, plan, "repair", lambda p: None)
    assert result["transferred_bytes"] == len(xml_path.read_bytes())
    assert xml_path.with_name(xml_path.name + ".rlm-backup-repair").read_bytes() == original
    repaired = parse_xml(xml_path.read_bytes())
    assert repaired.findtext("folder/name") == game.title
    assert repaired.findtext("game/playcount") == "12"
    assert repaired.findtext("game/path") == root.findtext("game/path")
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before} == before

    repeat = build_plan(remote, config(), [game], options(game))
    writes = remote.sftp.writes
    assert repeat["required_bytes"] == 0
    assert perform_sync(remote, repeat, "repeat", lambda p: None)["transferred_bytes"] == 0
    assert remote.sftp.writes == writes


def test_unknown_catalog_title_is_reported_for_review(tmp_path, remote):
    game = game_at(tmp_path)
    game.title = "RLM-" + "a" * 24
    plan = build_plan(remote, config(), [game], options(game))
    assert plan["title_reviews"][0]["game_id"] == game.id
    assert "titolo da revisionare" in " ".join(plan["warnings"])


@pytest.mark.parametrize(
    "xml", [b'<!DOCTYPE a [<!ENTITY x "bad">]><gameList>&x;</gameList>', b"<wrong/>", b"<broken>"]
)
def test_xml_rejects_unsafe_or_invalid(xml):
    with pytest.raises((ValueError, ParseError, DefusedXmlException)):
        merge_gamelist(xml, [], "/roms/gb")


def test_conflict_is_blocked_without_overwrite(tmp_path, remote):
    game = game_at(tmp_path)
    plan = build_plan(remote, config(), [game], options(game))
    perform_sync(remote, plan, "first", lambda p: None)
    path = remote.sftp.resolve(plan["groups"][0]["files"][0]["path"])
    path.write_bytes(b"other content")
    next_plan = build_plan(remote, config(), [game], options(game))
    assert not next_plan["can_sync"] and next_plan["groups"][0]["files"][0]["state"] == "modified"
    with pytest.raises(ValueError, match="cambiato"):
        perform_sync(remote, plan, "second", lambda p: None)
    assert path.read_bytes() == b"other content"


def test_space_limits_rechecked(tmp_path, remote):
    game = game_at(tmp_path)
    plan = build_plan(remote, config(), [game], options(game))
    remote.free = 1
    assert not build_plan(remote, config(), [game], options(game))["can_sync"]
    with pytest.raises(ValueError, match="Spazio"):
        perform_sync(remote, plan, "small", lambda p: None)
    assert remote.sftp.writes == 0


@pytest.mark.parametrize("multidisc", [False, True])
def test_cancel_removes_only_own_staging_and_never_publishes_partial(tmp_path, remote, multidisc):
    game = game_at(tmp_path, multidisc)
    plan = build_plan(remote, config(), [game], options(game))
    unrelated = remote.sftp.resolve("/home/pi/RetroPie/roms/gb/user.txt")
    unrelated.write_text("keep")

    def cancel(progress):
        if progress.get("file_bytes", 0) > 0:
            raise SyncCancelled()

    with pytest.raises(SyncCancelled):
        perform_sync(remote, plan, "cancel-test", cancel)
    assert not remote.sftp.resolve(plan["groups"][0]["path"]).exists()
    assert not list(remote.sftp.root.rglob(".rlm-stage-cancel-test*"))
    assert unrelated.read_text() == "keep"
    perform_sync(remote, plan, "retry", lambda p: None)
    assert all(remote.sftp.resolve(f["path"]).is_file() for f in plan["groups"][0]["files"])
    if multidisc:
        assert len(plan["groups"][0]["files"]) == 5


def test_resume_validates_partial_prefix_and_hash(remote):
    fs = SafeRemote(remote, ["/home/pi/RetroPie/roms"])
    path = "/home/pi/RetroPie/roms/gb/.part"
    payload = b"abc" * 80000
    sha = hashlib.sha256(payload).hexdigest()
    remote.sftp.resolve(path).write_bytes(payload[:20000])
    progress = []
    fs.upload(path, io.BytesIO(payload), len(payload), sha, progress.append)
    assert 20000 in progress and fs.hash(path) == sha
    remote.sftp.resolve(path).write_bytes(b"bad prefix")
    fs.upload(path, io.BytesIO(payload), len(payload), sha, lambda p: None)
    assert fs.hash(path) == sha
    with pytest.raises(ValueError, match="SHA-256"):
        fs.upload(path, io.BytesIO(payload), len(payload), "0" * 64, lambda p: None)
    assert not remote.sftp.resolve(path).exists()


@pytest.mark.parametrize(
    "path",
    [
        "/home/pi/RetroPie/roms/../BIOS/x",
        "/etc/passwd",
        "/home/pi/RetroPie/roms/gb/../../x",
        "/home/pi/RetroPie/roms/gb/a\\b",
    ],
)
def test_remote_path_traversal(remote, path):
    with pytest.raises(ValueError):
        SafeRemote(remote, ["/home/pi/RetroPie/roms"]).path(path)


def test_remote_symlink_and_permissions(remote, tmp_path, monkeypatch):
    remote.sftp.links.add("/home/pi/RetroPie/roms/gb")
    game = game_at(tmp_path)
    with pytest.raises(ValueError, match="Symlink"):
        build_plan(remote, config(), [game], options(game))
    remote.sftp.links.clear()
    original = remote.sftp.lstat

    def forbidden(path):
        if path.endswith(".gb"):
            raise PermissionError(13, "Permission denied")
        return original(path)

    monkeypatch.setattr(remote.sftp, "lstat", forbidden)
    with pytest.raises(PermissionError):
        build_plan(remote, config(), [game], options(game))


def test_missing_and_changed_sources(tmp_path, remote):
    game = game_at(tmp_path)
    plan = build_plan(remote, config(), [game], options(game))
    Path(game.local_path).write_bytes(b"changed")
    with pytest.raises(ValueError, match="modificato"):
        perform_sync(remote, plan, "changed", lambda p: None)
    Path(game.local_path).unlink()
    with pytest.raises(FileNotFoundError):
        build_plan(remote, config(), [game], options(game))


def test_chd_requires_core_confirmation(tmp_path, remote):
    game = game_at(tmp_path)
    game.files[0]["path"] = str(tmp_path / "game.chd")
    Path(game.files[0]["path"]).write_bytes(b"x")
    game.files[0].update(relative="game.chd", size=1, sha256=hashlib.sha256(b"x").hexdigest())
    game.local_path = game.files[0]["path"]
    game.platform = "psx"
    game.format = "chd"
    assert not build_plan(remote, config(), [game], options(game))["can_sync"]
    assert build_plan(remote, {**config(), "chd_confirmed": True}, [game], options(game))["can_sync"]


def test_existing_gamelist_backup_and_live_es_deferral(tmp_path, remote):
    game = game_at(tmp_path)
    path = remote.sftp.resolve("/home/pi/RetroPie/roms/gb/gamelist.xml")
    original = (
        b"<gameList><game><path>./user.gb</path><name>Existing</name><custom>keep</custom></game></gameList>"
    )
    path.write_bytes(original)
    remote.running = True
    plan = build_plan(remote, config(), [game], options(game))
    result = perform_sync(remote, plan, "running", lambda p: None)
    assert result["metadata_deferred"] and path.read_bytes() == original
    remote.running = False
    plan = build_plan(remote, config(), [game], options(game))
    result = perform_sync(remote, plan, "stopped", lambda p: None)
    assert not result["metadata_deferred"] and result["backups"]
    assert remote.sftp.resolve(result["backups"][0]).read_bytes() == original
    assert parse_xml(path.read_bytes()).findtext("game/custom") == "keep"


def test_metadata_changed_after_preview_is_preserved(tmp_path, remote):
    game = game_at(tmp_path)
    plan = build_plan(remote, config(), [game], options(game))
    path = remote.sftp.resolve(plan["gamelists"][0]["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"<gameList><folder><path>./custom</path></folder></gameList>")
    with pytest.raises(ValueError, match="gamelist cambiata"):
        perform_sync(remote, plan, "race", lambda p: None)
    assert b"custom" in path.read_bytes()


def wait_run(client, run_id):
    for _ in range(200):
        value = client.get("/api/sync/runs/" + run_id).json()
        if value["status"] not in {"preparing", "queued", "running", "retry_wait", "cancelling"}:
            return value
        time.sleep(0.02)
    raise AssertionError("Sync timeout")


def test_device_api_confirmation_retry_and_persistence(tmp_path, remote, monkeypatch):
    data = tmp_path / "data"
    app = create_app(data)
    with TestClient(app, headers={"X-RLM-Request": "1"}) as client:
        app.state.devices.connect = lambda config: remote
        body = DeviceInput(name="Pi", host="retropie", is_default=True).model_dump()
        device = client.post("/api/devices", json=body).json()["id"]
        game = game_at(tmp_path)
        with app.state.sessions.begin() as db:
            db.add(game)
        run_id = client.post("/api/sync/plans", json={"device_id": device, "game_ids": [1]}).json()["id"]
        assert wait_run(client, run_id)["status"] == "preview"
        assert client.post(f"/api/sync/runs/{run_id}/confirm", json={"confirmed": True}).status_code == 422
        original = remote.sftp.rename

        def fail(*args):
            raise OSError("Connection interrupted")

        monkeypatch.setattr(remote.sftp, "rename", fail)
        monkeypatch.setattr(app.state.devices.stop, "wait", lambda seconds: False)
        assert (
            client.post(
                f"/api/sync/runs/{run_id}/confirm", json={"confirmed": True, "rights_confirmed": True}
            ).status_code
            == 200
        )
        assert wait_run(client, run_id)["status"] == "failed"
        monkeypatch.setattr(remote.sftp, "rename", original)
        assert client.post(f"/api/sync/runs/{run_id}/control", json={"action": "retry"}).status_code == 200
        assert wait_run(client, run_id)["status"] == "completed"
    with TestClient(create_app(data)) as client:
        assert client.get("/api/devices").json()[0]["config"]["host"] == "retropie"
        assert client.get(f"/api/sync/runs/{run_id}").json()["status"] == "completed"


def test_interrupted_run_recovers_without_automatic_transfer(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app):
        with app.state.sessions.begin() as db:
            db.add(SyncRun(id="interrupted", device_id="gone", status="running"))
    with TestClient(create_app(tmp_path / "data")) as client:
        assert client.get("/api/sync/runs/interrupted").json()["status"] == "failed"


def test_ssh_reject_policy_and_no_password(monkeypatch, tmp_path):
    path = tmp_path / "ssh"
    path.mkdir()
    (path / "known_hosts").write_text("")
    monkeypatch.setenv("RLM_SSH_DIR", str(path))
    observed = {}

    class Client:
        def load_host_keys(self, path):
            observed["hosts"] = path

        def set_missing_host_key_policy(self, policy):
            observed["policy"] = policy

        def connect(self, *args, **kwargs):
            observed.update(kwargs)
            raise paramiko.AuthenticationException("Key rejected")

        def close(self):
            observed["closed"] = True

    monkeypatch.setattr("backend.ssh_connection.paramiko.SSHClient", Client)
    with pytest.raises(paramiko.AuthenticationException):
        with SSHConnection(config()):
            pass
    assert isinstance(observed["policy"], paramiko.RejectPolicy)
    assert observed["allow_agent"] is False and observed["look_for_keys"] is False
    assert "password" not in observed and observed["closed"]


def test_unknown_host_requires_confirmation():
    with pytest.raises(ValueError, match="fingerprint"):
        with SSHConnection({**config(), "fingerprint": ""}):
            pass


def test_no_shell_interpolation_in_remote_paths(remote):
    from backend.remote_fs import SPACE, rpc

    path = "/home/pi/RetroPie/roms/a'; touch /tmp/not-executed; '"
    observed = []
    original = remote.execute
    remote.execute = lambda command: observed.append(command) or original(command)
    rpc(remote, SPACE, {"path": path})
    assert path not in observed[0]
    assert (
        base64.b64encode(path.encode()).decode() not in observed[0]
    )  # It is encoded as JSON, not a shell fragment.


def test_cover_deduplication_and_missing_image(tmp_path, remote):
    game = game_at(tmp_path)
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"synthetic image payload")
    game.cover_path = str(cover)
    plan = build_plan(remote, config(), [game], options(game, covers=True))
    assert len(plan["media"]) == 1
    perform_sync(remote, plan, "cover", lambda p: None)
    second = build_plan(remote, config(), [game], options(game, covers=True))
    assert second["media"][0]["state"] == "present" and second["required_bytes"] == 0
    xml = remote.sftp.resolve(plan["gamelists"][0]["path"]).read_bytes()
    image = parse_xml(xml).findtext("game/image")
    assert remote.sftp.resolve("/home/pi/RetroPie/roms/gb/" + image).exists()
    cover.unlink()
    missing = build_plan(remote, config(), [game], options(game, covers=True))
    assert missing["warnings"] and not missing["media"]


def test_changed_host_key_is_rejected(monkeypatch):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from backend.ssh_connection import probe

    def key():
        raw = Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption()
        )
        return paramiko.Ed25519Key(file_obj=io.StringIO(raw.decode()))

    saved, changed = key(), key()
    hosts = paramiko.HostKeys()
    hosts.add("retropie", "ssh-ed25519", saved)

    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class Transport(Socket):
        def __init__(self, sock):
            pass

        def get_security_options(self):
            return type("Options", (), {})()

        def start_client(self, timeout):
            pass

        def get_remote_server_key(self):
            return changed

    monkeypatch.setattr("backend.ssh_connection.socket.create_connection", lambda *a, **k: Socket())
    monkeypatch.setattr("backend.ssh_connection.paramiko.Transport", Transport)
    monkeypatch.setattr("backend.ssh_connection.known_keys", lambda: hosts)
    with pytest.raises(ValueError, match="Host key cambiata"):
        probe("retropie", 22)


def test_authorized_keys_backup_and_idempotent_install(tmp_path, monkeypatch):
    import os
    import sys

    from backend.ssh_setup import INSTALL

    folder = tmp_path / ".ssh"
    folder.mkdir()
    target = folder / "authorized_keys"
    old = b"ssh-ed25519 existing-public-test-key user\n"
    target.write_bytes(old)
    key = "ssh-ed25519 added-public-test-key rlm-local"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(os, "getuid", lambda: target.stat().st_uid, raising=False)
    monkeypatch.setattr(sys, "argv", ["installer", base64.b64encode(key.encode()).decode()])
    exec(INSTALL, {})
    backups = list(folder.glob("authorized_keys.rlm-backup-*"))
    assert len(backups) == 1 and backups[0].read_bytes() == old
    assert target.read_bytes() == old + key.encode() + b"\n"
    with pytest.raises(SystemExit) as result:
        exec(INSTALL, {})
    assert result.value.code == 0
    assert len(list(folder.glob("authorized_keys.rlm-backup-*"))) == 1
