import pytest
from remote_fixture import FakeConnection
from test_sync import config, game_at, options

from backend.es_collections import parse_settings, serialize_settings
from backend.gamelist import parse_xml
from backend.sync_engine import build_plan, perform_sync


def setup(tmp_path):
    remote = FakeConnection(tmp_path / "remote")
    remote.collections_supported = True
    settings = remote.sftp.resolve("/opt/retropie/configs/all/emulationstation/es_settings.cfg")
    settings.write_bytes(
        b'<?xml version="1.0"?>\n<!--keep--><string name="CollectionSystemsCustom" value="My Collection"/>\n<int name="ScreenWidth" value="1920"/>\n'
    )
    game = game_at(tmp_path)
    game._rlm_classic = True
    game._rlm_position = 1
    return remote, game, settings


def test_collection_settings_backup_no_rom_changes_and_incremental_repeat(tmp_path):
    remote, game, settings = setup(tmp_path)
    original_settings = settings.read_bytes()
    initial = build_plan(remote, config(), [game], options(game))
    perform_sync(remote, initial, "original", lambda p: None)
    rom = remote.sftp.resolve(initial["groups"][0]["files"][0]["path"])
    save = rom.with_suffix(".srm")
    save.write_bytes(b"battery save")
    before = (rom.read_bytes(), save.read_bytes())
    plan = build_plan(remote, config(), [game], options(game, collection=True))
    assert plan["collection_support"]["members"] == 1
    assert remote.sftp.writes > 0  # Earlier ROM transfer, never from the dry-run.
    result = perform_sync(remote, plan, "collections", lambda p: None)
    collection = next(f for f in plan["gamelists"] if f["kind"] == "collection")
    lines = remote.sftp.resolve(collection["path"]).read_text(encoding="utf-8").splitlines()
    assert lines == ["/" + rom.relative_to(remote.sftp.root).as_posix()]
    root, _ = parse_settings(settings.read_bytes())
    assert root.find("string").get("value") == "My Collection,Grandi Classici"
    assert root.find("int").get("value") == "1920" and b"<!--keep-->" in settings.read_bytes()
    assert settings.with_name(settings.name + ".rlm-backup-collections").read_bytes() == original_settings
    assert (rom.read_bytes(), save.read_bytes()) == before
    assert not result["metadata_deferred"]
    repeated = build_plan(remote, config(), [game], options(game, collection=True))
    writes = remote.sftp.writes
    assert repeated["required_bytes"] == 0
    assert perform_sync(remote, repeated, "repeat", lambda p: None)["transferred_bytes"] == 0
    assert remote.sftp.writes == writes


def test_collection_respects_running_es_and_unsupported_versions(tmp_path):
    remote, game, settings = setup(tmp_path)
    original = settings.read_bytes()
    remote.running = True
    plan = build_plan(remote, config(), [game], options(game, collection=True))
    result = perform_sync(remote, plan, "running", lambda p: None)
    assert result["metadata_deferred"] and settings.read_bytes() == original
    assert not any(x["status"] == "updated" for x in result["gamelists"])
    remote.collections_supported = False
    unsupported = build_plan(remote, config(), [game], options(game, collection=True))
    assert not unsupported["collection_support"]["supported"]
    assert not any(f["kind"] in {"collection", "es_settings"} for f in unsupported["gamelists"])
    assert any("disponibile in Windows" in w for w in unsupported["warnings"])


def test_remove_membership_preserves_foreign_entries_and_roms(tmp_path):
    remote, game, _ = setup(tmp_path)
    plan = build_plan(remote, config(), [game], options(game, collection=True))
    perform_sync(remote, plan, "first", lambda p: None)
    collection = next(f for f in plan["gamelists"] if f["kind"] == "collection")
    path = remote.sftp.resolve(collection["path"])
    path.write_text(
        path.read_text(encoding="utf-8")
        + "/home/pi/RetroPie/roms/nes/user-game.nes\n/home/pi/RetroPie/roms/nes/rlm-unknown/game.nes\n",
        encoding="utf-8",
    )
    game._rlm_classic = False
    updated = build_plan(remote, config(), [game], options(game, collection=True))
    perform_sync(remote, updated, "remove", lambda p: None)
    assert path.read_text(encoding="utf-8").splitlines() == [
        "/home/pi/RetroPie/roms/nes/user-game.nes",
        "/home/pi/RetroPie/roms/nes/rlm-unknown/game.nes",
    ]
    assert remote.sftp.resolve(plan["groups"][0]["files"][0]["path"]).is_file()


def test_cover_and_screenshot_use_supported_distinct_xml_fields(tmp_path):
    remote, game, _ = setup(tmp_path)
    cover = tmp_path / "cover.png"
    screenshot = tmp_path / "screenshot.png"
    cover.write_bytes(b"synthetic cover")
    screenshot.write_bytes(b"synthetic screenshot")
    game.cover_path = str(cover)
    game._rlm_screenshot = str(screenshot)
    plan = build_plan(remote, config(), [game], options(game, covers=True, screenshots=True))
    assert {m["kind"] for m in plan["media"]} == {"cover", "screenshot"}
    perform_sync(remote, plan, "images", lambda p: None)
    root = parse_xml(remote.sftp.resolve(plan["gamelists"][0]["path"]).read_bytes())
    assert root.findtext("game/image") != root.findtext("game/thumbnail")
    assert root.findtext("folder/image") == root.findtext("game/image")
    assert root.findtext("folder/thumbnail") == root.findtext("game/thumbnail")
    assert (
        build_plan(remote, config(), [game], options(game, covers=True, screenshots=True))["required_bytes"]
        == 0
    )


def test_collection_config_changed_after_preview_is_not_overwritten(tmp_path):
    remote, game, settings = setup(tmp_path)
    plan = build_plan(remote, config(), [game], options(game, collection=True))
    settings.write_bytes(
        b'<?xml version="1.0"?>\n<string name="CollectionSystemsCustom" value="User edit"/>\n'
    )
    with pytest.raises(ValueError, match="cambiat|cambiat|modificat"):
        perform_sync(remote, plan, "stale", lambda p: None)
    assert b"User edit" in settings.read_bytes()


def test_actual_retropie_settings_fragment_keeps_video_maps_and_unicode():
    original = '<?xml version="1.0"?>\n<bool name="MoveCarousel" value="true" />\n<int name="ScreenRotate" value="0" />\n<float name="ScreenSaverTime" value="300" />\n<string name="ThemeSet" value="carbon-2021" />\n<map name="RandomCollectionSystems" type="int"><int name="NES &amp; GB" value="4" /></map>\n<string name="CollectionSystemsCustom" value="Preferiti è" />\n'.encode()
    root, header = parse_settings(original)
    before = [dict(x.attrib) for x in root]
    node = next(x for x in root if x.get("name") == "CollectionSystemsCustom")
    node.set("value", node.get("value") + ",Grandi Classici")
    updated = serialize_settings(root, header)
    assert b"<rlm-settings>" not in updated and b"<config>" not in updated
    parsed, _ = parse_settings(updated)
    assert [dict(x.attrib) for x in parsed][:-1] == before[:-1]
    assert parsed.find("map/int").get("name") == "NES & GB"
    assert parsed[-1].get("value") == "Preferiti è,Grandi Classici"
