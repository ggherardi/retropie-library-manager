import zlib

import pytest
from test_intelligence import archive, component, entry

from backend import neogeo_bios
from backend.arcade_archives import validate_set


@pytest.mark.parametrize(
    "case,complete",
    [
        ("valid", True),
        ("missing", False),
        ("bad", False),
        ("optional_bad", False),
        ("sha1_bad", False),
        ("unknown_revision", False),
    ],
)
def test_pinned_mvs_required_and_optional_integrity(tmp_path, monkeypatch, case, complete):
    payload = {
        name: (name + " synthetic firmware").encode()
        for name in [*sorted(neogeo_bios.REQUIRED), "neo-po.bin"]
    }
    parts = [component(name, data, crc=f"{zlib.crc32(data):08x}") for name, data in payload.items()]
    monkeypatch.setattr(neogeo_bios, "PARTS", {p["name"]: (p["size"], p["crc"]) for p in parts})
    bios = entry("neogeo", parts, kind="bios")
    program = component("program.bin", b"program")
    game = entry("demo", [program, *parts], romof="neogeo")
    files = {k: v for k, v in payload.items() if k in neogeo_bios.REQUIRED}
    if case == "missing":
        files.pop("sm1.sm1")
    if case == "bad":
        files["sm1.sm1"] = b"x" * len(payload["sm1.sm1"])
    if case == "optional_bad":
        files["neo-po.bin"] = b"x" * len(payload["neo-po.bin"])
    if case == "sha1_bad":
        bios["components"][0]["sha1"] = "0" * 40
        game["components"][1]["sha1"] = "0" * 40
    source = {
        "core": "lr-fbneo",
        "official_verified": True,
        "revision": neogeo_bios.REVISION if case != "unknown_revision" else "0" * 40,
    }
    paths = {
        "demo": archive(tmp_path, "demo", {"program.bin": b"program"}),
        "neogeo": archive(tmp_path, "neogeo", files),
    }
    report = validate_set(game, {"demo": game, "neogeo": bios}, paths, "non-merged", source_config=source)
    assert report["launchable"] is complete, report
    if complete:
        assert report["optional_bios"][0]["file"] == "neo-po.bin"


def test_shared_bios_dry_run_repeat_conflict_and_space(tmp_path, monkeypatch):
    from remote_fixture import FakeConnection
    from test_sync import config

    import backend.core_profiles as profiles

    payload = {name: name.encode() for name in neogeo_bios.REQUIRED}
    parts = [component(name, data, crc=f"{zlib.crc32(data):08x}") for name, data in payload.items()]
    monkeypatch.setattr(neogeo_bios, "PARTS", {p["name"]: (p["size"], p["crc"]) for p in parts})
    monkeypatch.setattr(neogeo_bios, "check_mvs_configuration", lambda connection: {})
    monkeypatch.setattr(
        profiles,
        "audit_cores",
        lambda *args: {"cores": {"lr-fbneo": {"installed": True, "version": "v1.0.0.03 af50579"}}},
    )
    source = {"core": "lr-fbneo", "official_verified": True, "revision": neogeo_bios.REVISION}
    catalog = {"neogeo": entry("neogeo", parts, kind="bios")}
    path = archive(tmp_path, "neogeo", payload)
    remote = FakeConnection(tmp_path / "remote")
    before = path.read_bytes()
    plan = neogeo_bios.shared_bios(remote, config(), catalog, source, path)
    assert plan["dry_run"] and remote.sftp.writes == 0
    assert neogeo_bios.shared_bios(remote, config(), catalog, source, path, authorized=True)["verified"]
    writes = remote.sftp.writes
    assert (
        neogeo_bios.shared_bios(remote, config(), catalog, source, path, authorized=True)["state"]
        == "present"
    )
    assert remote.sftp.writes == writes and path.read_bytes() == before
    remote.free = 1000
    with pytest.raises(ValueError, match="4 GiB"):
        neogeo_bios.shared_bios(remote, config(), catalog, source, path)
    remote.free = 27000000000
    remote.sftp.resolve(plan["path"]).write_bytes(b"different")
    with pytest.raises(ValueError, match="sovrascrittura"):
        neogeo_bios.shared_bios(remote, config(), catalog, source, path, authorized=True)


@pytest.mark.parametrize("mode", ["DIPSWITCH", "AES_JAP", "custom"])
def test_configuration_parser_rejects_unsupported_options(tmp_path, monkeypatch, mode):
    import contextlib
    import io
    import json

    def local_path(value):
        return tmp_path / str(value).lstrip("/")

    all_root = local_path("/opt/retropie/configs/all")
    neo_root = local_path("/opt/retropie/configs/neogeo")
    all_root.mkdir(parents=True)
    neo_root.mkdir(parents=True)
    command = "/opt/retropie/emulators/retroarch/bin/retroarch -L /opt/retropie/libretrocores/lr-fbneo/fbneo_libretro.so --config /opt/retropie/configs/neogeo/retroarch.cfg %ROM%"
    (neo_root / "emulators.cfg").write_text('lr-fbneo = "' + command + '"')
    options = (
        "/unverified/options.cfg"
        if mode == "custom"
        else "/opt/retropie/configs/all/retroarch-core-options.cfg"
    )
    (all_root / "retroarch.cfg").write_text('core_options_path = "' + options + '"')
    (all_root / "retroarch-core-options.cfg").write_text('fbneo-neogeo-mode = "' + mode + '"')

    def execute_script(connection, code, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(code.replace("pathlib.Path(", "local_path("), {"local_path": local_path})
        return json.loads(output.getvalue())

    monkeypatch.setattr(neogeo_bios, "rpc", execute_script)
    if mode != "DIPSWITCH":
        with pytest.raises(ValueError, match="non applicabile"):
            neogeo_bios.check_mvs_configuration(object())
    else:
        assert neogeo_bios.check_mvs_configuration(object())["conflicts"] == []
