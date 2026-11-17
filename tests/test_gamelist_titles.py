import pytest

from backend.gamelist import merge_gamelist, parse_xml

GROUP = "rlm-01b764db2ebd393c37388e89"


@pytest.mark.parametrize(
    "platform,title,filename",
    [("nes", "F-FF", "F-FF.nes"), ("gb", "2048gb", "2048.gb"), ("mame-libretro", "Gridlee", "gridlee.zip")],
)
def test_game_and_managed_folder_have_readable_names(platform, title, filename):
    game = {"title": title, "launch": f"{GROUP}/{filename}", "image": "./.rlm-media/cover.png"}
    merged = merge_gamelist(None, [game], f"/roms/{platform}")
    root = parse_xml(merged)
    assert root.findtext("game/name") == root.findtext("folder/name") == title
    assert root.findtext("folder/path") == "./" + GROUP
    assert root.findtext("folder/image") == game["image"]
    assert merge_gamelist(merged, [game], f"/roms/{platform}") == merged


def test_preserves_correct_metadata_and_matches_absolute_folder_path():
    existing = f"""<gameList><!--keep--><game id="original"><path>./{GROUP}/F-FF.nes</path><name>F-FF</name><playcount>12</playcount><lastplayed>20261117T090000</lastplayed><favorite>true</favorite><custom>keep</custom></game><folder id="folder"><path>/roms/nes/{GROUP}</path><name>RLM-01B764DB2EBD393C37388E89</name><desc>Keep this description</desc><custom>keep folder</custom></folder><folder><path>./My games</path><name>My games</name></folder></gameList>""".encode()
    game = {"title": "F-FF", "launch": GROUP + "/F-FF.nes"}
    merged = merge_gamelist(existing, [game], "/roms/nes")
    root = parse_xml(merged)
    assert root.find("game").attrib == {"id": "original"}
    for field in ("playcount", "lastplayed", "favorite", "custom"):
        assert root.findtext("game/" + field) == parse_xml(existing).findtext("game/" + field)
    folders = root.findall("folder")
    assert len(folders) == 2 and folders[0].attrib == {"id": "folder"}
    assert folders[0].findtext("name") == "F-FF"
    assert folders[0].findtext("desc") == "Keep this description"
    assert folders[0].findtext("custom") == "keep folder"
    assert folders[1].findtext("name") == "My games"
    assert b"<!--keep-->" in merged
    assert merge_gamelist(merged, [game], "/roms/nes") == merged


@pytest.mark.parametrize("title", ["", "RLM-01B764DB2EBD393C37388E89", "a" * 64])
@pytest.mark.parametrize(
    "filename,expected",
    [
        ("Known Original.gb", "Known Original"),
        ("track01.bin", "Titolo da verificare"),
        ("discs.m3u", "Titolo da verificare"),
        ("b" * 64 + ".gb", "Titolo da verificare"),
    ],
)
def test_missing_titles_are_conservative_and_review_remains_visible(title, filename, expected):
    game = {"game_id": 7, "title": title, "launch": f"{GROUP}/{filename}"}
    reviews = []
    merged = merge_gamelist(None, [game], "/roms/gb", reviews)
    assert parse_xml(merged).findtext("folder/name") == expected
    assert reviews == [{"game_id": 7, "launch": game["launch"], "title": expected}]
    second_reviews = []
    assert merge_gamelist(merged, [game], "/roms/gb", second_reviews) == merged
    assert second_reviews == reviews


def test_existing_readable_metadata_precedes_filename_fallback():
    game = {"title": "RLM-" + "a" * 24, "launch": GROUP + "/track01.bin"}
    existing = f"<gameList><game><path>./{game['launch']}</path><name>Verified remote title</name></game></gameList>".encode()
    merged = merge_gamelist(existing, [game], "/roms/psx")
    assert parse_xml(merged).findtext("folder/name") == "Verified remote title"


def test_emulationstation_omitted_default_favorite_is_preserved():
    game = {"title": "Bootee", "launch": GROUP + "/Bootee.nes", "favorite": False}
    existing = f"<gameList><game><path>./{game['launch']}</path><name>Bootee</name><playcount>2</playcount></game></gameList>".encode()
    merged = merge_gamelist(existing, [game], "/roms/nes")
    assert parse_xml(merged).find("game/favorite") is None
    assert parse_xml(merged).findtext("game/playcount") == "2"
    game["favorite"] = True
    marked = merge_gamelist(merged, [game], "/roms/nes")
    assert parse_xml(marked).findtext("game/favorite") == "true"
    game["favorite"] = False
    assert parse_xml(merge_gamelist(marked, [game], "/roms/nes")).findtext("game/favorite") == "false"


def test_shared_user_folders_are_not_relabelled():
    games = [{"title": title, "launch": f"My games/{title}.gb"} for title in ("One", "Two")]
    merged = merge_gamelist(None, games, "/roms/gb")
    assert parse_xml(merged).find("folder") is None


def test_multidisc_group_uses_one_folder_and_keeps_launch_path():
    game = {"title": "Verified title", "launch": GROUP + "/discs.m3u"}
    merged = merge_gamelist(None, [game], "/roms/psx")
    root = parse_xml(merged)
    assert len(root.findall("folder")) == 1
    assert root.findtext("game/path") == "./" + game["launch"]


def test_duplicate_folder_paths_and_conflicting_titles_are_rejected():
    game = {"title": "One", "launch": GROUP + "/one.gb"}
    existing = f"<gameList><folder><path>./{GROUP}</path></folder><folder><path>/roms/gb/{GROUP}</path></folder></gameList>".encode()
    with pytest.raises(ValueError, match="Più record XML folder"):
        merge_gamelist(existing, [game], "/roms/gb")
    with pytest.raises(ValueError, match="Titoli discordanti"):
        merge_gamelist(None, [game, {"title": "Two", "launch": GROUP + "/two.gb"}], "/roms/gb")


@pytest.mark.parametrize("launch", ["../game.gb", "/game.gb", "folder/../../game.gb", "folder\\game.gb"])
def test_invalid_launch_paths_are_rejected(launch):
    with pytest.raises(ValueError, match="Percorso"):
        merge_gamelist(None, [{"launch": launch, "title": "Game"}], "/roms/gb")
