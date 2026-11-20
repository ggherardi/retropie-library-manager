import hashlib
import io
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from backend.db import DiscoveryEntry, EssentialClassic, Game, GameInsight, MediaAsset
from backend.main import create_app
from backend.scanner import candidate


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.network.validate_url", lambda url: None)
    root = tmp_path / "roms"
    root.mkdir()
    app = create_app(tmp_path / "data")
    with TestClient(app, headers={"X-RLM-Request": "1"}) as client:
        client.put("/api/settings", json={"import_roots": [str(root)], "export_root": str(root)})
        yield app, client, root


def game(app, root, name="Same title", data=b"synthetic fixture", platform="gb"):
    path = root / (name + ".gb")
    path.write_bytes(data)
    values = candidate([path], root, platform)
    values.pop("entrypoints")
    with app.state.sessions.begin() as db:
        row = Game(**values)
        db.add(row)
        db.flush()
        return row.id


def run(client, response, expected="completed"):
    assert response.status_code == 202, response.text
    for _ in range(300):
        result = client.get("/api/intelligence/runs/" + response.json()["id"]).json()
        if result["status"] in {"completed", "failed", "cancelled"}:
            assert result["status"] == expected, result
            return result["result"] if expected == "completed" else result
        time.sleep(0.02)
    pytest.fail("Operation timed out")


def add_classic(app, content, platform="gb", suffix=""):
    identity = "fixture-classic" + suffix
    with app.state.sessions.begin() as db:
        db.add(
            EssentialClassic(
                id=identity,
                title="Same title",
                platform=platform,
                genre="Puzzle",
                year=1990,
                details={"identifiers": [{"hashes": [{"sha1": hashlib.sha1(content).hexdigest()}]}]},
            )
        )
    return identity


def test_bundled_catalog_is_large_sourced_and_metadata_only(library):
    app, client, _ = library
    summary = client.get("/api/collections/summary").json()
    assert summary["catalogued"] >= 500
    assert summary["present_classics"] == 0 and summary["missing_classics"] == summary["catalogued"]
    with app.state.sessions() as db:
        rows = list(db.scalars(select(EssentialClassic)))
        assert {
            "nes",
            "snes",
            "megadrive",
            "mastersystem",
            "gb",
            "gbc",
            "gba",
            "pcengine",
            "neogeo",
            "mame-libretro",
            "psx",
        } <= {r.platform for r in rows}
        for row in rows:
            assert row.details["identifiers"] and row.details["sources"]
            assert row.details["availability"] == "local_copy_required"
            assert row.details["license"] is None and "rating" not in row.details
        titles = {r.title for r in rows}
        assert {
            "Super Mario Bros.",
            "Super Mario World",
            "Chrono Trigger",
            "Sonic the Hedgehog",
            "Crash Team Racing",
            "Tekken 3",
            "Gran Turismo 2",
        } <= titles


def test_hash_matching_separates_owned_missing_excluded_and_duplicates(library):
    app, client, root = library
    data = b"verified synthetic cartridge"
    gid = game(app, root, data=data)
    classic = add_classic(app, data)
    result = run(client, client.post("/api/collections/match"))
    assert result["matched"] == [
        {"game_id": gid, "classic_id": classic, "basis": "SHA-1 DAT e SHA-256 locale verificati"}
    ]
    assert client.get("/api/collections/owned?view=classics").json()["total"] == 1
    assert client.get("/api/collections/summary").json()["present_classics"] == 1
    assert not any(
        x["id"] == classic for x in client.get("/api/collections/classics?q=Same%20title").json()["items"]
    )
    client.put(f"/api/collections/games/{gid}", json={"mode": "exclude"})
    assert client.get("/api/collections/owned?view=classics").json()["total"] == 0
    assert client.get("/api/collections/summary").json()["present_classics"] == 1
    assert client.get("/api/collections/owned").json()["total"] == 1
    run(client, client.post("/api/collections/match"))
    assert client.get("/api/collections/owned?view=classics").json()["total"] == 0
    add_classic(app, data, suffix="duplicate")
    result = run(client, client.post("/api/collections/match"))
    assert not result["matched"] and "ambigua" in result["unresolved"][0]["reason"]


def test_similar_titles_wrong_platform_missing_files_and_manual_identity(library):
    app, client, root = library
    gid = game(app, root, data=b"not matching")
    classic = add_classic(app, b"other game")
    add_classic(app, b"not matching", platform="nes", suffix="nes")
    assert not run(client, client.post("/api/collections/match"))["matched"]
    assert (
        client.put(
            f"/api/collections/games/{gid}", json={"mode": "include", "classic_id": classic}
        ).status_code
        == 400
    )
    assert (
        client.put(
            f"/api/collections/games/{gid}",
            json={"mode": "include", "classic_id": classic, "identity_confirmed": True, "position": 8},
        ).status_code
        == 200
    )
    assert client.get("/api/collections/owned?view=classics&sort=manual").json()["items"][0]["position"] == 8
    (root / "Same title.gb").unlink()
    assert client.get("/api/collections/owned?view=classics").json()["total"] == 0
    assert client.get("/api/collections/summary").json()["present_classics"] == 0
    assert client.get("/api/collections/owned?availability=missing_file").json()["total"] == 1


def test_quality_unknown_fields_and_stale_review(library):
    app, client, root = library
    gid = game(app, root)
    summary = client.get("/api/collections/summary").json()
    assert summary["covers"] == summary["screenshots"] == 0
    assert summary["fields"]["year"]["percent"] == 0
    assert summary["fields"]["title"]["percent"] == 100
    assert (
        client.put(
            f"/api/collections/games/{gid}/review", json={"status": "verified", "note": "short"}
        ).status_code
        == 400
    )
    assert (
        client.put(
            f"/api/collections/games/{gid}/review",
            json={"status": "verified", "note": "Verified against the original author source"},
        ).status_code
        == 200
    )
    assert client.get("/api/collections/owned?metadata_status=verified").json()["total"] == 1
    with app.state.sessions.begin() as db:
        db.get(Game, gid).title = "Changed title"
    assert client.get("/api/collections/owned?metadata_status=review").json()["total"] == 1


def source(app, game_id, *, correct=True, multiple=False):
    out = io.BytesIO()
    Image.new("RGB", (8, 8), "green").save(out, format="PNG")
    image = out.getvalue()
    sha = hashlib.sha1(f"blob {len(image)}\0".encode() + image).hexdigest()
    assets = [
        {
            "kind": kind,
            "url": "https://assets.example/image.png",
            "license": "CC0-1.0",
            "git_blob_sha1": sha if correct else "0" * 40,
            "source_url": "https://author.example/permission",
        }
        for kind in (["cover", "screenshot", "screenshot"] if multiple else ["cover", "screenshot"])
    ]
    with app.state.sessions.begin() as db:
        owned = db.get(Game, game_id)
        db.add(
            DiscoveryEntry(
                id="verified-source",
                provider_id="gbdev",
                external_id="fixture",
                title=owned.title,
                platform=owned.platform,
                available=True,
                sha256=owned.sha256,
                source_url="https://author.example",
                payload={"media": assets},
            )
        )

    def transport(request):
        return httpx.Response(
            200, content=b"User-agent: *\nAllow: /" if request.url.path == "/robots.txt" else image
        )

    app.state.acquisition.http.client.close()
    app.state.acquisition.http.client = httpx.Client(transport=httpx.MockTransport(transport))
    return image


def test_authorized_media_preview_apply_cache_and_repeat(library):
    app, client, root = library
    gid = game(app, root)
    source(app, gid)
    plan = run(client, client.post("/api/media/plans", json={}))
    assert len(plan["candidates"]) == 2
    assert (
        client.get(
            f"/api/media/plans/{plan['id']}/candidates/{plan['candidates'][0]['id']}/image"
        ).status_code
        == 200
    )
    assert client.get("/api/collections/summary").json()["covers"] == 0
    body = {"confirmed": True, "candidate_ids": [x["id"] for x in plan["candidates"]]}
    result = run(client, client.post(f"/api/media/plans/{plan['id']}/confirm", json=body))
    assert len(result["applied"]) == 2 and not result["failed"]
    assert client.get(f"/api/media/games/{gid}/screenshot").status_code == 200
    assert client.get(f"/api/games/{gid}/cover").status_code == 200
    assert client.get(f"/api/intelligence/games/{gid}/screenshot").status_code == 200
    assert client.get("/api/collections/summary").json()["screenshots"] == 1
    assert run(client, client.post(f"/api/media/plans/{plan['id']}/confirm", json=body)) == result
    assert not run(client, client.post("/api/media/plans", json={}))["candidates"]
    with app.state.sessions() as db:
        assert len(list(db.scalars(select(MediaAsset)))) == 2


def test_media_rejects_wrong_integrity_ambiguity_and_forged_candidates(library):
    app, client, root = library
    gid = game(app, root)
    source(app, gid, correct=False, multiple=True)
    plan = run(client, client.post("/api/media/plans", json={}))
    run(
        client,
        client.post(
            f"/api/media/plans/{plan['id']}/confirm",
            json={"confirmed": True, "candidate_ids": [x["id"] for x in plan["candidates"]]},
        ),
        "failed",
    )
    run(
        client,
        client.post(
            f"/api/media/plans/{plan['id']}/confirm", json={"confirmed": True, "candidate_ids": ["forged"]}
        ),
        "failed",
    )
    result = run(
        client,
        client.post(
            f"/api/media/plans/{plan['id']}/confirm",
            json={"confirmed": True, "candidate_ids": [plan["candidates"][0]["id"]]},
        ),
    )
    assert result["failed"] and not result["applied"]
    assert "Hash media" in result["failed"][0]["error"]
    assert client.get("/api/collections/summary").json()["covers"] == 0


def test_local_media_requires_authorized_root_and_retains_previous(library, tmp_path):
    app, client, root = library
    gid = game(app, root)
    image = source(app, gid)
    outside = tmp_path / "outside.png"
    outside.write_bytes(image)
    body = {
        "kind": "screenshot",
        "path": str(outside),
        "rights_confirmed": True,
        "identity_confirmed": True,
        "source": "Own captured screenshot",
        "license": "Personal authorized capture",
    }
    assert client.post(f"/api/media/games/{gid}/local", json=body).status_code == 400
    inside = root / "capture.png"
    inside.write_bytes(image)
    body["path"] = str(inside)
    assert client.post(f"/api/media/games/{gid}/local", json=body).status_code == 200
    assert (
        client.put(
            f"/api/collections/games/{gid}/review",
            json={"status": "verified", "note": "Screenshot checked against the original game"},
        ).status_code
        == 200
    )
    assert client.get("/api/collections/owned?metadata_status=verified").json()["total"] == 1
    replacement = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(replacement, format="PNG")
    inside.write_bytes(replacement.getvalue())
    assert client.post(f"/api/media/games/{gid}/local", json=body).status_code == 200
    assert client.get("/api/collections/owned?metadata_status=review").json()["total"] == 1
    history = client.get(f"/api/media/games/{gid}/history").json()
    assert len(history) == 2 and sum(x["active"] for x in history) == 1
    assert all(Path(x["path"]).is_file() for x in history)
    with app.state.sessions() as db:
        assert db.get(GameInsight, gid).test_status == "untested"


def test_recovery_priority_orders_existing_classics_before_alphabetic(library):
    app, client, _ = library
    with app.state.sessions.begin() as db:
        rows = list(db.scalars(select(EssentialClassic).order_by(EssentialClassic.title.desc()).limit(2)))
        first, second = rows
        first.details = {**first.details, "recovery_priority": 1}
        second.details = {**second.details, "recovery_priority": 2}
        expected = [first.id, second.id]
    result = client.get("/api/collections/classics?page_size=2").json()
    assert [r["id"] for r in result["items"]] == expected
    assert result["items"][0]["details"]["recovery_priority"] == 1
