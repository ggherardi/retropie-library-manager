import hashlib
import zipfile
from pathlib import Path

import pytest
from rar_fixtures import rar, upstream
from test_archive_import import packed, ready
from test_installations import confirm, create, disc, finished, nes, wait
from test_installations import setup as setup
from test_intelligence import component, import_rows

from backend.archive_import import ArchiveStore, Budget, inventory
from backend.archive_volumes import source_parts
from backend.db import InstallationItem


@pytest.mark.parametrize("version", [4, 5])
def test_rar_real_decoder_install_incremental(setup, version):
    _, client, source, remote, _ = setup
    payload = nes(source / "fixture.nes").read_bytes()
    path = rar(source / "game.rar", {"Folder/Readable.nes": payload}, version)
    original = path.read_bytes()
    batch = create(client, [path])
    assert len(ready(batch)) == 1, batch
    assert ready(batch)[0]["platform"] == "nes"
    confirm(client, batch)
    installed = finished(client, batch)
    assert installed["counts"]["installed"] == 1
    assert remote.sftp.writes > 0
    writes = remote.sftp.writes
    second = create(client, [path])
    confirm(client, second)
    assert finished(client, second)["counts"]["installed"] == 1
    assert remote.sftp.writes == writes and path.read_bytes() == original
    assert client.get("/api/stats").json()["games"] == 1


@pytest.mark.parametrize("version", [4, 5])
def test_rar_ps1_multitrack_and_other_games(setup, version):
    _, client, source, _, _ = setup
    folder = source / "input"
    folder.mkdir()
    cue = disc(folder)
    cue.write_text(cue.read_text() + 'FILE "Audio.bin" BINARY\n TRACK 02 AUDIO\n INDEX 01 00:00:00\n')
    files = {p.name: p.read_bytes() for p in folder.iterdir()}
    files["Audio.bin"] = bytes(2352 * 4)
    files["Other.nes"] = nes(source / "other.nes").read_bytes()
    files["scph1001.bin"] = b"synthetic BIOS accessory"
    path = rar(source / "mixed.rar", files, version)
    batch = create(client, [path])
    assert sorted(i["platform"] for i in ready(batch)) == ["nes", "psx"], batch
    ps1 = next(i for i in ready(batch) if i["platform"] == "psx")
    assert len(ps1["candidate"]["files"]) == 3
    confirm(client, batch)
    assert finished(client, batch)["counts"]["installed"] == 2


@pytest.mark.parametrize("extension", [".zip", ".7z"])
def test_rar_nested_in_zip_or_7z(setup, extension):
    _, client, source, _, _ = setup
    inner = rar(source / "inner.rar", {"Game.nes": nes(source / "game.nes").read_bytes()})
    outer = packed(source, "outer" + extension, {"Folder/inner.rar": inner.read_bytes()})
    batch = create(client, [outer])
    assert len(ready(batch)) == 1, batch
    confirm(client, batch)
    assert finished(client, batch)["counts"]["installed"] == 1


@pytest.mark.parametrize("extension", [".zip", ".7z"])
def test_byte_split_volumes_grouped_once_with_automatic_install(setup, extension):
    _, client, source, _, _ = setup
    path = packed(source, "split" + extension, {"Game.nes": nes(source / "fixture.nes").read_bytes()})
    raw = path.read_bytes()
    size = max(1, len(raw) // 3)
    parts = []
    for i, start in enumerate(range(0, len(raw), size), 1):
        part = source / (path.name + f".{i:03d}")
        part.write_bytes(raw[start : start + size])
        parts.append(part)
    originals = [p.read_bytes() for p in parts]
    batch = create(client, list(reversed(parts)))
    assert len(ready(batch)) == 1 and batch["counts"]["prepared"] == 1, batch
    confirm(client, batch)
    assert finished(client, batch)["counts"]["installed"] == 1
    assert [p.read_bytes() for p in parts] == originals


@pytest.mark.parametrize("name", ["rar3-solid.rar", "rar5-solid.rar"])
def test_compressed_solid_rar_actual_decoding(tmp_path, name):
    path = upstream(tmp_path, [name])[0]
    store = ArchiveStore(tmp_path / "data")
    prepared, report = store.prepare(path, inventory(path), Budget(lambda: None))
    assert len(report["files"]) == 2
    assert (prepared / "stest1.txt").read_bytes() == (prepared / "stest2.txt").read_bytes()
    assert (prepared / "stest1.txt").stat().st_size == 2048


@pytest.mark.parametrize("family", ["rar3-vols", "rar5-vols", "rar3-old"])
def test_rar_volume_formats_actual_decoding_and_originals(tmp_path, family):
    names = [
        family + ext
        for ext in (
            [".rar", ".r00", ".r01"] if family.endswith("old") else [f".part{i}.rar" for i in range(1, 4)]
        )
    ]
    parts = upstream(tmp_path, names)
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in parts]
    first, found, kind, _ = source_parts(parts[-1])
    assert first == parts[0] and set(found) == set(parts) and kind == "rar"
    prepared, report = ArchiveStore(tmp_path / "data").prepare(first, inventory(first), Budget(lambda: None))
    assert sum(f["size"] for f in report["files"].values()) >= 205000
    assert len(report["source_files"]) == 3
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in parts] == hashes
    assert all((prepared / name).is_file() for name in report["files"])


@pytest.mark.parametrize("missing", ["first", "middle", "last"])
def test_missing_rar_volume_diagnosis(tmp_path, missing):
    names = [f"rar5-vols.part{i}.rar" for i in range(1, 4)]
    absent = {"first": 0, "middle": 1, "last": 2}[missing]
    parts = upstream(tmp_path, [n for i, n in enumerate(names) if i != absent])
    with pytest.raises(ValueError, match="(?i)volume|incompleto|troncato"):
        entries = inventory(parts[0])
        ArchiveStore(tmp_path / "data").prepare(parts[0], entries, Budget(lambda: None))


@pytest.mark.parametrize("name", ["rar3-comment-psw.rar", "rar5-hpsw.rar"])
def test_protected_rar_has_precise_error(tmp_path, name):
    path = upstream(tmp_path, [name])[0]
    with pytest.raises(ValueError, match="(?i)password|cifrat"):
        inventory(path)


@pytest.mark.parametrize(
    "name", ["../escape.nes", "C:/escape.nes", "NUL.nes", "folder/../escape.nes", "file.nes:stream"]
)
def test_rar_member_traversal_rejected(tmp_path, name):
    path = rar(tmp_path / "bad.rar", {name: b"data"})
    with pytest.raises(ValueError, match="(?i)sicur|percorso"):
        inventory(path)


def test_rar_corrupt_crc_keeps_original_and_cleans_staging(tmp_path):
    path = rar(tmp_path / "broken.rar", {"file.bin": b"unique payload"})
    path.write_bytes(path.read_bytes().replace(b"unique payload", b"broken payload"))
    original = path.read_bytes()
    store = ArchiveStore(tmp_path / "data")
    with pytest.raises(ValueError, match="(?i)corrotto|crc"):
        store.prepare(path, inventory(path), Budget(lambda: None))
    assert path.read_bytes() == original and not list(store.work.iterdir())


def test_old_unsupported_rar_job_reanalysis_without_upload(setup):
    app, client, source, _, _ = setup
    path = rar(source / "game.rar", {"Game.nes": nes(source / "fixture.nes").read_bytes()})
    batch = create(client, [path])
    container = next(i for i in batch["items"] if i["status"] == "prepared")
    with app.state.sessions.begin() as db:
        row = db.get(InstallationItem, container["id"])
        row.status = "awaiting_decision"
        row.identification = {"reason": "RAR unsupported in previous version"}
    confirm(client, batch)
    assert client.post(f"/api/installations/items/{container['id']}/reanalyze").status_code == 202
    result = wait(
        client,
        batch["id"],
        lambda b: b["counts"].get("installed") == 1 and not b["counts"].get("reanalyzing"),
    )
    assert result["counts"]["prepared"] == 1 and result["total"] == 2


@pytest.mark.parametrize("extension", [".rar", ".7z"])
def test_arcade_repacked_only_after_complete_dat_and_bios(setup, extension):
    app, client, source, _, _ = setup
    program, bios = b"program contents", b"synthetic firmware"
    import_rows(
        client,
        source,
        [
            {
                "name": "neogeo",
                "kind": "bios",
                "platform": "neogeo",
                "components": [component("bios.bin", bios)],
            },
            {
                "name": "game",
                "title": "Verified Arcade",
                "platform": "neogeo",
                "romof": "neogeo",
                "components": [component("program.bin", program)],
            },
        ],
    )
    path = (
        rar(source / "game.rar", {"program.bin": program})
        if extension == ".rar"
        else packed(source, "game.7z", {"program.bin": program})
    )
    original = path.read_bytes()
    incomplete = create(client, [path], mode="local")
    assert not ready(incomplete), incomplete
    assert not list(app.state.installations.archives.store.root.glob("v*/*.zip"))
    # A RAR BIOS is validated as a dependency and converted, never installed as a game.
    rar(source / "neogeo.rar", {"bios.bin": bios})
    complete = create(client, [path], mode="local")
    assert len(ready(complete)) == 1, complete
    item = ready(complete)[0]
    assert item["candidate"]["format"] == "zip" and item["identification"]["archive"]["repacked_zip"]
    with zipfile.ZipFile(item["candidate"]["local_path"]) as archive_file:
        assert archive_file.read("program.bin") == program
    assert all(
        Path(a["path"]).suffix == ".zip"
        for a in item["identification"]["chosen"]["report"]["archives"].values()
    )
    assert path.read_bytes() == original
    confirm(client, complete)
    assert finished(client, complete)["counts"]["imported_local"] == 1


def test_spanned_zip_z01_and_final_zip_install(setup):
    from rar_fixtures import split_zip

    _, client, source, _, _ = setup
    parts = split_zip(source, "spanned", nes(source / "fixture.nes").read_bytes())
    batch = create(client, parts)
    assert len(ready(batch)) == 1 and batch["counts"]["prepared"] == 1, batch
    confirm(client, batch)
    assert finished(client, batch)["counts"]["installed"] == 1


def test_arcade_equivalent_rar_reuses_existing_zip_and_paths(setup):
    _, client, source, _, _ = setup
    data = b"verified arcade program"
    import_rows(
        client,
        source,
        [
            {
                "name": "game",
                "title": "Verified Game",
                "platform": "arcade",
                "components": [component("program.bin", data)],
            }
        ],
    )
    first = packed(source, "game.zip", {"program.bin": data})
    batch = create(client, [first], mode="local")
    confirm(client, batch)
    finished(client, batch)
    second = rar(source / "game.rar", {"program.bin": data})
    repeat = create(client, [second], mode="local")
    assert len(ready(repeat)) == 1, repeat
    assert ready(repeat)[0]["candidate"]["local_path"] == str(first)
    assert ready(repeat)[0]["identification"]["duplicate"]
    confirm(client, repeat)
    finished(client, repeat)
    assert client.get("/api/stats").json()["games"] == 1


def test_missing_decoder_is_actionable(tmp_path, monkeypatch):
    monkeypatch.setenv("RLM_7ZIP", str(tmp_path / "not-installed.exe"))
    path = rar(tmp_path / "game.rar", {"game.nes": b"data"})
    with pytest.raises(ValueError, match="7-Zip assente.*Setup"):
        inventory(path)


def test_invalid_rar_signature_is_not_a_game(setup):
    _, client, source, _, _ = setup
    path = source / "fake.rar"
    path.write_bytes(b"not an archive")
    batch = create(client, [path])
    assert batch["counts"] == {"failed": 1}
    assert "Firma RAR non valida" in batch["items"][0]["identification"]["reason"]


@pytest.mark.parametrize("extension", [".zip", ".7z"])
def test_missing_byte_split_volume_and_changed_volume_never_reuses_cache(tmp_path, extension):
    raw_path = packed(tmp_path, "set" + extension, {"data.bin": bytes(range(256)) * 20})
    raw = raw_path.read_bytes()
    boundary = len(raw) // 2
    first, second = tmp_path / (raw_path.name + ".001"), tmp_path / (raw_path.name + ".002")
    first.write_bytes(raw[:boundary])
    second.write_bytes(raw[boundary:])
    store = ArchiveStore(tmp_path / "data")
    prepared, report = store.prepare(first, inventory(first), Budget(lambda: None))
    old = (prepared / "data.bin").read_bytes()
    second.write_bytes(bytes(len(raw) - boundary))
    with pytest.raises(ValueError):
        store.prepare(first, inventory(first), Budget(lambda: None))
    assert (prepared / "data.bin").read_bytes() == old


@pytest.mark.parametrize("extension", [".zip", ".7z"])
def test_encrypted_zip_7z_rejected_by_real_decoder(tmp_path, extension):
    import subprocess

    from backend.archive_engine import engine

    source = tmp_path / "payload.txt"
    source.write_text("synthetic encrypted fixture")
    path = tmp_path / ("protected" + extension)
    subprocess.run(
        [engine(), "a", "-pfixture-password", str(path), str(source)],
        check=True,
        stdout=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    with pytest.raises(ValueError, match="(?i)cifrat|password"):
        inventory(path)


def test_tekken_layout_nested_ecm_and_ape_is_one_noninstallable_archive(setup):
    _, client, source, _, _ = setup
    inner = packed(source, "Track 1.7z", {"Track 1.bin.ecm": b"ECM\0" + bytes(100)})
    outer = rar(
        source / "Disc.rar",
        {
            "Folder/Track 1.7z": inner.read_bytes(),
            "Folder/Track 2.ape": b"MAC " + bytes(100),
            "Folder/Track 3.ape": b"MAC " + bytes(50),
        },
        4,
    )
    batch = create(client, [outer])
    assert batch["counts"] == {"awaiting_decision": 1}, batch
    info = batch["items"][0]["identification"]
    assert info["unsupported_formats"] == ["APE", "ECM"]
    assert "CUE/M3U assente" in info["reason"] and "45434d00" in info["signatures"].values()
    assert client.get("/api/stats").json()["games"] == 0


@pytest.mark.parametrize("extension", [".zip", ".7z"])
def test_missing_final_byte_volume_has_actionable_diagnostic(tmp_path, extension):
    path = packed(tmp_path, "missing" + extension, {"file.bin": bytes(range(256)) * 20})
    raw = path.read_bytes()
    part = tmp_path / (path.name + ".001")
    part.write_bytes(raw[: len(raw) // 2])
    with pytest.raises(ValueError, match="suddiviso incompleto.*tutti i volumi.*Rianalizza"):
        inventory(part)


def test_nested_volume_archive_continues_past_unsupported_audio(setup):
    _, client, source, _, _ = setup
    inner = packed(source, "inner.7z", {"Game.nes": nes(source / "fixture.nes").read_bytes()}).read_bytes()
    middle = len(inner) // 2
    outer = rar(
        source / "nested.rar",
        {"inner.7z.001": inner[:middle], "inner.7z.002": inner[middle:], "audio.ape": b"MAC " + bytes(100)},
    )
    batch = create(client, [outer], mode="local")
    assert len(ready(batch)) == 1 and batch["counts"]["awaiting_decision"] == 1, batch
    confirm(client, batch)
    result = wait(client, batch["id"], lambda b: b["counts"].get("imported_local") == 1)
    assert result["counts"]["prepared"] == 2


@pytest.mark.parametrize("name", ["@payload.nes", "-payload.nes"])
def test_rar_members_are_literal_names_not_cli_arguments(tmp_path, name):
    path = rar(tmp_path / "literal.rar", {name: b"literal member bytes"})
    prepared, report = ArchiveStore(tmp_path / "data").prepare(path, inventory(path), Budget(lambda: None))
    assert (prepared / name).read_bytes() == b"literal member bytes"
    assert set(report["files"]) == {name}
