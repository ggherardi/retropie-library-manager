import hashlib
import stat
import zipfile
from pathlib import Path

import py7zr
import pytest
from sqlalchemy import select
from test_installations import confirm, create, disc, finished, nes, wait
from test_installations import setup as setup
from test_intelligence import archive, component, import_rows

from backend.archive_import import ArchiveStore, Budget, inventory
from backend.db import InstallationItem


def packed(source, name, files):
    path = source / name
    if path.suffix == ".zip":
        with zipfile.ZipFile(path, "w") as target:
            for relative, content in files.items():
                target.writestr(relative, content)
    else:
        with py7zr.SevenZipFile(path, "w") as target:
            for relative, content in files.items():
                target.writestr(content, relative)
    return path


def ready(batch):
    return [i for i in batch["items"] if i["status"] == "ready"]


@pytest.mark.parametrize("platform,extension", [("nes", ".zip"), ("megadrive", ".7z"), ("gb", ".zip")])
def test_cartridge_archive_automatic_install_and_repeat(setup, platform, extension):
    _, client, source, remote, _ = setup
    if platform == "nes":
        payload = nes(source / "fixture.nes").read_bytes()
        name = "Readable.nes"
    elif platform == "megadrive":
        data = bytearray(32768)
        data[0x100:0x104] = b"SEGA"
        payload, name = bytes(data), "Readable.gen"
    else:
        data = bytearray(32768)
        data[0x104:0x108] = bytes.fromhex("ceed6666")
        data[0x14D] = (-sum(data[0x134:0x14D]) - 25) & 255
        payload, name = bytes(data), "Readable.gb"
    path = packed(source, "bundle" + extension, {name: payload, "README.md": b"documentation"})
    original = path.read_bytes()
    batch = create(client, [path])
    assert len(ready(batch)) == 1, batch
    assert ready(batch)[0]["platform"] == platform
    assert ready(batch)[0]["candidate"]["files"][0]["sha256"] == hashlib.sha256(payload).hexdigest()
    confirm(client, batch)
    assert finished(client, batch)["counts"]["installed"] == 1
    writes = remote.sftp.writes
    second = create(client, [path])
    assert ready(second)[0]["identification"]["duplicate"]
    confirm(client, second)
    assert finished(client, second)["counts"]["installed"] == 1
    assert remote.sftp.writes == writes
    assert path.read_bytes() == original
    assert client.get("/api/stats").json()["games"] == 1


@pytest.mark.parametrize("kind", ["single", "tracks", "multidisc", "playlist"])
def test_ps1_7z_group_complete_discs_and_tracks(setup, kind):
    _, client, source, _, _ = setup
    folder = source / "disc-input"
    folder.mkdir()
    cue = disc(folder, "Known (Disc 1)")
    if kind == "tracks":
        (folder / "Audio.bin").write_bytes(bytes(2352 * 4))
        cue.write_text(cue.read_text() + 'FILE "Audio.bin" BINARY\n TRACK 02 AUDIO\n INDEX 01 00:00:00\n')
    if kind in {"multidisc", "playlist"}:
        second = disc(folder, "Known (Disc 2)")
        if kind == "playlist":
            (folder / "Known.m3u").write_text(cue.name + "\n" + second.name + "\n")
    files = {p.name: p.read_bytes() for p in folder.iterdir()}
    path = packed(source, "PlayStation.7z", files)
    batch = create(client, [path])
    assert len(ready(batch)) == 1, batch
    assert ready(batch)[0]["platform"] == "psx"
    assert len(ready(batch)[0]["candidate"]["files"]) == len(files)
    confirm(client, batch)
    assert finished(client, batch)["counts"]["installed"] == 1


def test_multiple_games_nested_archives_and_bios_exclusion(setup):
    _, client, source, _, _ = setup
    first = nes(source / "first.nes").read_bytes()
    second = nes(source / "second.nes", 2).read_bytes()
    nested = packed(source, "nested.7z", {"Other.nes": second})
    path = packed(
        source,
        "collection.zip",
        {
            "One.nes": first,
            "nested.7z": nested.read_bytes(),
            "scph1001.bin": b"firmware-not-a-game",
            "README.md": b"doc",
        },
    )
    batch = create(client, [path], mode="local")
    assert len(ready(batch)) == 2
    confirm(client, batch)
    assert finished(client, batch)["counts"]["imported_local"] == 2


def test_incomplete_disc_does_not_create_separate_tracks_or_block_other_game(setup):
    _, client, source, _, _ = setup
    folder = source / "disc-input"
    folder.mkdir()
    cue = disc(folder, "Known")
    cue.write_text(cue.read_text() + 'FILE "Missing audio.bin" BINARY\n TRACK 02 AUDIO\n INDEX 01 00:00:00\n')
    files = {p.name: p.read_bytes() for p in folder.iterdir()}
    files["Complete.nes"] = nes(source / "fixture.nes").read_bytes()
    path = packed(source, "mixed.zip", files)
    batch = create(client, [path])
    assert len(ready(batch)) == 1 and batch["counts"]["awaiting_decision"] == 1, batch
    issue = next(i for i in batch["items"] if i["status"] == "awaiting_decision")
    assert "Missing audio.bin" in issue["identification"]["reason"]
    confirm(client, batch)
    result = wait(client, batch["id"], lambda b: b["counts"].get("installed") == 1)
    assert result["counts"]["awaiting_decision"] == 1


def test_ecm_archive_reports_missing_descriptor_and_associated_audio(setup):
    _, client, source, _, _ = setup
    path = packed(source, "Disc.7z", {"Track1.bin.ecm": b"ECM\x00" + bytes(100)})
    (source / "Track2.ape").write_bytes(b"MAC " + bytes(100))
    batch = create(client, [path])
    assert batch["counts"] == {"awaiting_decision": 1}
    info = batch["items"][0]["identification"]
    assert "ECM" in info["reason"] and "CUE" in info["reason"]
    assert info["associated_files"] == ["Track2.ape"]
    assert info["signatures"]["Track1.bin.ecm"] == b"ECM\x00".hex()


@pytest.mark.parametrize(
    "name",
    [
        "../escape.nes",
        "/absolute.nes",
        "C:/absolute.nes",
        "folder/../escape.nes",
        "NUL.nes",
        "file.nes:stream",
        "trailing./rom.nes",
        "A\\..\\escape.nes",
    ],
)
def test_archive_traversal_and_windows_names_rejected(tmp_path, name):
    path = packed(tmp_path, "bad.zip", {name: b"payload"})
    with pytest.raises(ValueError, match="non sicuro"):
        inventory(path)


@pytest.mark.parametrize("kind", ["case", "file_directory", "symlink", "bomb", "corrupt"])
def test_malicious_or_corrupt_archives_never_published(setup, kind):
    app, client, source, _, _ = setup
    path = source / "bad.zip"
    if kind == "corrupt":
        path.write_bytes(b"not a zip")
    else:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            if kind == "case":
                z.writestr("game.nes", b"a")
                z.writestr("GAME.NES", b"a")
            elif kind == "file_directory":
                z.writestr("file", b"a")
                z.writestr("file/rom.nes", b"b")
            elif kind == "symlink":
                entry = zipfile.ZipInfo("link")
                entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                z.writestr(entry, "../target")
            else:
                z.writestr("bomb.nes", bytes(2 * 1024**2))
    batch = create(client, [path])
    assert batch["counts"] == {"failed": 1}, batch
    assert client.get("/api/stats").json()["games"] == 0
    assert not list(app.state.installations.archives.store.root.glob("v*"))


def test_nested_depth_and_cumulative_limits(tmp_path, monkeypatch):
    import backend.archive_import as module

    path = packed(tmp_path, "nested.zip", {"rom.bin": bytes(100)})
    store = ArchiveStore(tmp_path / "data")
    with pytest.raises(ValueError, match="profondità"):
        store.prepare(path, inventory(path), Budget(lambda: None), depth=4)
    monkeypatch.setattr(module, "MAX_TOTAL", 150)
    budget = Budget(lambda: None)
    budget.bytes = 75
    with pytest.raises(ValueError, match="cumulativa"):
        store.prepare(path, inventory(path), budget)


def test_retry_and_reanalyze_old_authorized_job_without_upload(setup):
    app, client, source, _, _ = setup
    path = packed(source, "known.zip", {"Game.nes": nes(source / "fixture.nes").read_bytes()})
    # An existing Increment 7 job has no prepared children and was waiting on arcade identification.
    old = app.state.installations.archives.analyze
    app.state.installations.archives.analyze = lambda p, *_: [
        (
            p,
            {
                "status": "awaiting_decision",
                "candidate": {},
                "consumed": [p],
                "identification": {"title": "known", "reason": "Old ambiguous result"},
            },
        )
    ]
    batch = create(client, [path])
    confirm(client, batch)
    app.state.installations.archives.analyze = old
    item = batch["items"][0]
    response = client.post(f"/api/installations/items/{item['id']}/reanalyze")
    assert response.status_code == 202
    result = wait(client, batch["id"], lambda b: b["counts"].get("installed") == 1)
    assert result["total"] == 2 and client.get("/api/stats").json()["games"] == 1
    with app.state.sessions() as db:
        parent = db.scalar(select(InstallationItem).where(InstallationItem.id == item["id"]))
        assert parent.source_key == str(path)


def test_extraction_cleanup_recovery_and_integrity(tmp_path):
    path = packed(tmp_path, "game.7z", {"game.bin": b"data" * 1000})
    original = path.read_bytes()
    store = ArchiveStore(tmp_path / "data")
    store.recover()
    calls = 0

    def interrupt():
        nonlocal calls
        calls += 1
        if calls == 4:
            raise RuntimeError("interrupted")

    with pytest.raises(RuntimeError):
        store.prepare(path, inventory(path), Budget(interrupt))
    assert not list(store.work.iterdir())
    orphan = store.work / "work-interrupted"
    orphan.mkdir()
    (orphan / "partial").write_bytes(b"partial")
    store.recover()
    assert not orphan.exists()
    prepared, report = store.prepare(path, inventory(path), Budget(lambda: None))
    assert store.prepare(path, inventory(path), Budget(lambda: None))[0] == prepared
    assert path.read_bytes() == original and report["expanded_bytes"] == 4000
    (prepared / "game.bin").write_bytes(b"modified")
    with pytest.raises(ValueError, match="modificata"):
        store.prepare(path, inventory(path), Budget(lambda: None))
    assert (prepared / "game.bin").read_bytes() == b"modified"


def test_arcade_and_neogeo_archives_remain_compressed(setup):
    app, client, source, _, _ = setup
    program, firmware = b"program contents", b"synthetic BIOS"
    rows = [
        {
            "name": "neogeo",
            "kind": "bios",
            "platform": "neogeo",
            "components": [component("bios.bin", firmware)],
        },
        {
            "name": "game",
            "title": "Verified Neo Game",
            "platform": "neogeo",
            "romof": "neogeo",
            "components": [component("program.bin", program)],
        },
    ]
    import_rows(client, source, rows)
    archive(source, "neogeo", {"bios.bin": firmware})
    path = archive(source, "game", {"program.bin": program})
    batch = create(client, [path], mode="local")
    assert len(ready(batch)) == 1, batch
    item = ready(batch)[0]
    assert item["candidate"]["local_path"] == str(path)
    assert item["candidate"]["format"] == "zip"
    assert not item["identification"]["archive"]["extracted"]
    assert not list(app.state.installations.archives.store.root.glob("v*"))


def test_descriptor_case_and_separator_normalized_only_in_prepared_copy(setup):
    _, client, source, _, _ = setup
    folder = source / "disc-input"
    folder.mkdir()
    cue = disc(folder, "Known")
    original_cue = cue.read_bytes().replace(b"Known.bin", b"Tracks\\KNOWN.BIN")
    path = packed(
        source,
        "disc.zip",
        {"Known.cue": original_cue, "Tracks/Known.bin": cue.with_suffix(".bin").read_bytes()},
    )
    batch = create(client, [path], mode="local")
    assert len(ready(batch)) == 1, batch
    prepared_cue = Path(ready(batch)[0]["candidate"]["local_path"])
    assert b"Tracks/Known.bin" in prepared_cue.read_bytes()
    with zipfile.ZipFile(path) as original:
        assert original.read("Known.cue") == original_cue


@pytest.mark.parametrize("preferred", [False, True])
def test_verified_variants_use_preference_or_one_decision(setup, preferred):
    app, client, source, _, _ = setup
    first = nes(source / "one.nes", 31).read_bytes()
    second = nes(source / "two.nes", 32).read_bytes()
    rows = [
        {
            "name": "original",
            "title": "Verified original",
            "platform": "nes",
            "components": [component("one.nes", first)],
        },
        {
            "name": "variant",
            "parent": "original",
            "title": "Verified variant",
            "platform": "nes",
            "components": [component("two.nes", second)],
        },
    ]
    import_rows(client, source, rows)
    if preferred:
        from backend.db import CatalogEntry

        with app.state.sessions() as db:
            uid = db.scalar(select(CatalogEntry.uid).where(CatalogEntry.name == "variant"))
        assert client.post("/api/intelligence/preferred", json={"uid": uid}).status_code == 200
    path = packed(source, "variants.zip", {"one.nes": first, "two.nes": second})
    batch = create(client, [path], mode="local")
    if preferred:
        assert len(ready(batch)) == 1 and ready(batch)[0]["title"] == "Verified variant"
    else:
        assert not ready(batch) and batch["counts"]["awaiting_decision"] == 1
        pending = next(i for i in batch["items"] if i["status"] == "awaiting_decision")
        choice = next(v for v in pending["identification"]["variants"] if v["title"] == "Verified variant")
        response = client.post(
            f"/api/installations/items/{pending['id']}/decision",
            json={"action": "choose", "variant_source": choice["source"]},
        )
        assert response.status_code == 200, response.text
    confirm(client, batch)
    assert finished(client, batch)["counts"]["imported_local"] == 1
    assert client.get("/api/stats").json()["games"] == 1


def test_corrupt_member_crc_and_retry_after_repair(setup):
    _, client, source, _, _ = setup
    payload = nes(source / "fixture.nes").read_bytes()
    path = packed(source, "bad.zip", {"Game.nes": payload})
    original = path.read_bytes()
    damaged = bytearray(original)
    index = damaged.index(b"NES\x1a")
    damaged[index + 15] ^= 1
    path.write_bytes(damaged)
    batch = create(client, [path])
    assert batch["counts"] == {"failed": 1}
    assert "CRC" in batch["items"][0]["error"]["cause"]
    path.write_bytes(original)
    confirm(client, batch)
    response = client.post(f"/api/installations/items/{batch['items'][0]['id']}/retry")
    assert response.status_code == 200
    assert wait(client, batch["id"], lambda b: b["counts"].get("installed") == 1)["counts"]["installed"] == 1


def test_resource_timeout_and_decoder_dictionary_limit(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import backend.archive_import as module

    monkeypatch.setattr(module, "MAX_SECONDS", -1)
    with pytest.raises(ValueError, match="tempo"):
        Budget(lambda: None).check()
    coder = {"method": bytes.fromhex("21"), "properties": bytes([40])}
    archive_header = SimpleNamespace(
        header=SimpleNamespace(
            main_streams=SimpleNamespace(
                unpackinfo=SimpleNamespace(folders=[SimpleNamespace(coders=[coder])])
            )
        )
    )
    with pytest.raises(ValueError, match="64 MiB"):
        module.check_7z_resources(archive_header)


@pytest.mark.parametrize("problem", ["ecm", "nested_corrupt"])
def test_problematic_member_does_not_block_other_games_in_same_archive(setup, problem):
    _, client, source, _, _ = setup
    files = {"Complete.nes": nes(source / "fixture.nes").read_bytes()}
    if problem == "ecm":
        files["Track.bin.ecm"] = b"ECM\x00" + bytes(100)
        files["Track2.ape"] = b"MAC " + bytes(50)
    else:
        files["Broken.zip"] = b"not a ZIP archive"
    path = packed(source, "Mixed.zip", files)
    batch = create(client, [path], mode="local")
    assert len(ready(batch)) == 1 and batch["counts"].get("awaiting_decision") == 1, batch
    confirm(client, batch)
    result = wait(client, batch["id"], lambda b: b["counts"].get("imported_local") == 1)
    assert result["counts"]["awaiting_decision"] == 1


def test_failed_archive_still_consumes_cumulative_budget(tmp_path, monkeypatch):
    import backend.archive_import as module

    path = packed(tmp_path, "corrupt.zip", {"rom.bin": b"A" * 1000})
    data = bytearray(path.read_bytes())
    data[data.index(b"A" * 20)] = ord("B")
    path.write_bytes(data)
    entries = inventory(path)
    monkeypatch.setattr(module, "MAX_TOTAL", 1500)
    budget = Budget(lambda: None)
    store = ArchiveStore(tmp_path / "data")
    with pytest.raises(ValueError, match="CRC"):
        store.prepare(path, entries, budget)
    assert budget.bytes == 1000
    with pytest.raises(ValueError, match="cumulativa"):
        store.prepare(path, entries, budget)


def test_summary_cannot_overwrite_concurrent_retry(setup):
    import threading

    from sqlalchemy import event

    app, client, source, _, _ = setup
    path = source / "broken.zip"
    path.write_bytes(b"broken")
    batch = create(client, [path])
    service = app.state.installations
    service.shutdown()
    confirm(client, batch)
    item_id = batch["items"][0]["id"]
    engine = service.sessions.kw["bind"]
    reading, release, retry_started, retry_done = (threading.Event() for _ in range(4))
    errors = []

    def gate(conn, cursor, statement, parameters, context, executemany):
        if (
            threading.current_thread().name == "summary-regression"
            and "SELECT installation_items.status" in statement
        ):
            reading.set()
            assert release.wait(5)

    def summarize():
        try:
            service.summarize(batch["id"])
        except BaseException as exc:
            errors.append(exc)

    def retry():
        try:
            retry_started.set()
            service.retry_item(item_id)
            retry_done.set()
        except BaseException as exc:
            errors.append(exc)

    event.listen(engine, "after_cursor_execute", gate)
    summary = threading.Thread(target=summarize, name="summary-regression")
    retrier = threading.Thread(target=retry)
    try:
        summary.start()
        assert reading.wait(5)
        retrier.start()
        assert retry_started.wait(5)
        assert not retry_done.wait(0.1), "Retry must serialize with the summary transaction"
    finally:
        release.set()
        summary.join(5)
        retrier.join(5)
        event.remove(engine, "after_cursor_execute", gate)
    assert not errors and retry_done.is_set()
    result = client.get("/api/installations/" + batch["id"]).json()
    assert result["status"] == "running" and result["counts"] == {"reanalyzing": 1}


@pytest.mark.parametrize("extension", [".rar", ".ecm", ".ape"])
def test_unsupported_container_has_explicit_diagnostic(setup, extension):
    _, client, source, _, _ = setup
    path = source / ("unsupported" + extension)
    path.write_bytes(b"unsupported format fixture")
    batch = create(client, [path])
    assert batch["counts"] == {"awaiting_decision": 1}
    assert extension.upper() in batch["items"][0]["identification"]["reason"]
    assert "non supportato" in batch["items"][0]["identification"]["reason"]
