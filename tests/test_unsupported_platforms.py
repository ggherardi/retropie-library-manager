import hashlib
from dataclasses import replace

import pytest
from test_archive_import import packed
from test_installations import confirm, create, wait
from test_installations import setup as setup

from backend import reference_arcade
from backend.content_checks import format_check


def test_reference_requires_game_fingerprints_and_preserves_mixed_contents():
    def inventory(*parts):
        return {str(i): {"size": size, "sha1": sha} for i, (size, sha) in enumerate(parts)}

    for game in reference_arcade.REFERENCE_GAMES:
        assert reference_arcade.recognize(inventory(*game.accessories)) is None
        for program in game.programs.values():
            data = inventory(*program)
            assert reference_arcade.recognize(data)["platform"] == game.platform
            assert reference_arcade.recognize({**data, "other.bin": {"size": 100, "sha1": "other"}}) is None
            data["0"]["size"] += 1
            assert reference_arcade.recognize(data) is None


def test_reference_game_is_one_blocked_card_even_after_confirm_or_manual_choice(setup, monkeypatch):
    _, client, source, remote, _ = setup
    payload = b"synthetic game program"
    game = replace(
        reference_arcade.REFERENCE_GAMES[0],
        programs={"fixture": frozenset({(len(payload), hashlib.sha1(payload).hexdigest())})},
    )
    monkeypatch.setattr(reference_arcade, "REFERENCE_GAMES", (game,))
    path = packed(source, "renamed.zip", {"unknown.bin": payload})
    batch = create(client, [path])
    (card,) = batch["cards"]
    assert card["title"] == game.title and card["platform_label"] == "Namco System 246"
    assert card["experience"]["label"] == "Console non supportata"
    assert card["experience"]["section"] == "attention"
    assert not card["candidate"] and "resolve" not in card["experience"]["actions"]
    assert batch["experience_summary"]["identified"] == batch["experience_summary"]["blocked"] == 1
    confirm(client, batch)
    assert (
        client.post(
            f"/api/installations/items/{card['id']}/decision",
            json={"action": "choose", "platform": "psx", "confirmed_title": True, "entry_uid": "other"},
        ).status_code
        == 400
    )
    assert client.post(f"/api/installations/items/{card['id']}/reanalyze").is_success
    again = wait(client, batch["id"], lambda b: b["counts"].get("unsupported_platform") == 1)
    assert again["cards"][0]["experience"]["state"] == "unsupported_platform"
    assert client.get("/api/stats").json()["games"] == 0 and remote.sftp.writes == 0


def test_valid_c64_tape_and_misleading_shortname(setup):
    _, client, source, _, _ = setup
    tape = b"C64-TAPE-RAW" + bytes([1, 0, 0, 0, 1, 0, 0, 0, 42])
    valid = packed(source, "cassette.zip", {"Arkanoid.tap": tape})
    wrong = packed(source, "soulclb3.zip", {"sc31001-na-a.ic002": b"unrelated"})
    bad = source / "broken.tap"
    bad.write_bytes(tape[:-1])
    with pytest.raises(ValueError, match="incompleta"):
        format_check(bad)
    batch = create(client, [valid, wrong])
    cards = {c["title"]: c for c in batch["cards"]}
    assert cards["Arkanoid"]["platform_label"] == "Commodore 64"
    assert cards["Arkanoid"]["experience"]["state"] == "unsupported_platform"
    assert cards["soulclb3"]["experience"]["code"] == "unidentified"


def test_reanalyzing_old_unidentified_chips_recovers_one_archive_card(setup, monkeypatch):
    _, client, source, _, _ = setup
    chip = b"unrecognized in the original preview"
    other = b"second program component"
    path = packed(source, "old-preview.zip", {"chip.bin": chip, "other.bin": other})
    batch = create(client, [path])
    assert len(batch["cards"]) == 2
    game = replace(
        reference_arcade.REFERENCE_GAMES[-1],
        programs={"fixture": frozenset((len(p), hashlib.sha1(p).hexdigest()) for p in (chip, other))},
    )
    monkeypatch.setattr(reference_arcade, "REFERENCE_GAMES", (game,))
    assert client.post(f"/api/installations/items/{batch['cards'][0]['id']}/reanalyze").is_success
    result = wait(client, batch["id"], lambda b: b["counts"].get("unsupported_platform") == 1)
    assert result["counts"] == {"ignored": 2, "unsupported_platform": 1}
    assert [c["title"] for c in result["cards"]] == ["Dragon's Lair"]
    assert not result["authorized"]


def test_bad_crc_and_html_are_not_platform_evidence(setup):
    _, client, source, _, _ = setup
    payload = b"synthetic bytes for a stored ZIP member"
    corrupt = packed(source, "soulclb3.zip", {"sc31001-na-a.ic002": payload})
    corrupt.write_bytes(corrupt.read_bytes().replace(payload, b"!" + payload[1:], 1))
    html = source / "boxing.zip"
    html.write_bytes(b"<html><title>400 Bad Request</title></html>")
    items = {c["title"]: c["experience"] for c in create(client, [corrupt, html])["cards"]}
    assert items["soulclb3"]["label"] == "Archivio corrotto"
    assert items["boxing"]["label"] == "Archivio non valido" and "HTML" in items["boxing"]["message"]
