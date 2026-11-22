from copy import deepcopy

import pytest
from test_installations import confirm, create, finished, nes
from test_installations import setup as setup

from backend.installation_experience import cards, metrics, view


def item(status="ready", **values):
    return {
        "id": "one",
        "batch_id": "batch",
        "created_at": "2026-11-22",
        "status": status,
        "source_key": "C:/input/Game.nes",
        "identification": {},
        "candidate": {},
        "progress": {},
        **values,
    }


def project(value, **batch):
    return {**value, "experience": view(value, {"authorized": True, "control": "run", **batch})}


@pytest.mark.parametrize(
    "status",
    [
        "queued",
        "reanalyzing",
        "ready",
        "validating",
        "importing",
        "enriching",
        "preparing_sync",
        "transferring",
        "verifying",
        "waiting_device",
    ],
)
def test_intermediate_phases_are_indeterminate_not_finished(status):
    result = project(item(status))["experience"]
    assert result["state"] == "working" and result["tone"] == "blue"
    assert result["progress"]["kind"] == "indeterminate"
    assert not result["files_verified"] and result["phase"]


@pytest.mark.parametrize("status", ["transferred", "present"])
def test_completed_requires_evidence_not_launch_or_visibility(status):
    result = project(item("installed", game_id=1, progress={"report": {"games": [{"status": status}]}}))[
        "experience"
    ]
    assert result["state"] == ("installed" if status == "transferred" else "already_installed")
    assert result["files_verified"] and not result["launched"]
    assert result["section"] == "completed" and "library" in result["actions"]
    assert "retry" not in result["actions"]


def test_unverified_installed_legacy_label_does_not_assert_verification():
    result = project(item("installed"))["experience"]
    assert not result["files_verified"] and result["state"] != "installed"


@pytest.mark.parametrize("status", ["preparing_sync", "pending_refresh", "failed"])
def test_verified_files_do_not_revert_to_transfer_during_metadata(status):
    result = project(
        item(
            status, progress={"reports": [{"games": [{"status": "transferred"}], "metadata_deferred": True}]}
        )
    )["experience"]
    assert result["files_verified"] and result["state"] == "console_update"
    assert result["section"] == "completed" and result["progress"]["kind"] == "none"


def test_visibility_and_title_review_independent_of_installation():
    result = project(
        item(
            "installed",
            visibility="operator_confirmed",
            game_id=1,
            progress={"metadata_review": True, "report": {"games": [{"status": "transferred"}]}},
        )
    )["experience"]
    assert result["state"] == "console_update" and result["code"] == "metadata_review"
    assert result["visibility"] == "operator_confirmed" and "retry" in result["actions"]


@pytest.mark.parametrize(
    "reason,code,state",
    [
        ("Dimensione ISO9660 incoerente: immagine incompleta", "incomplete_disc", "blocked"),
        ("ECM/APE non supportati; CUE assente", "unsupported_disc", "blocked"),
        ("Archivio corrotto CRC", "invalid_archive", "blocked"),
        ("Archivio protetto da password", "encrypted", "blocked"),
        ("BIOS PS1 mancante", "missing_bios", "intervention"),
        ("Gamelist cambiato dopo il dry-run", "metadata_changed", "intervention"),
        ("conflitto remoto", "remote_conflict", "intervention"),
        ("connection timed out", "temporary", "intervention"),
    ],
)
def test_legacy_structured_diagnosis(reason, code, state):
    result = project(item("failed", game_id=1, error={"cause": reason}))["experience"]
    assert (result["code"], result["state"]) == (code, state)
    assert result["message"] and result["next_step"]
    assert ("retry" in result["actions"]) == (state == "intervention")


def test_shared_bios_report_is_an_intervention_not_game_rom_failure():
    value = item(
        "awaiting_decision",
        identification={
            "candidates": [
                {"report": {"bios": ["neogeo"], "problems": [{"set": "neogeo", "file": "bios.bin"}]}}
            ]
        },
    )
    result = project(value)["experience"]
    assert result["code"] == "missing_bios" and result["tone"] == "yellow"


def test_only_transfer_bytes_have_measured_progress():
    value = item("transferring", progress={"sync": {"bytes": 300, "total": 200}})
    assert project(value)["experience"]["progress"] == {"kind": "bytes", "value": 200, "total": 200}
    value["status"] = "verifying"
    assert project(value)["experience"]["progress"] == {"kind": "indeterminate"}


def test_metrics_distinguish_unique_copies_from_operations_and_scanning():
    first = project(
        item(
            "installed",
            game_id=1,
            candidate={"sha256": "same"},
            progress={"report": {"games": [{"status": "present"}]}},
        )
    )
    second = deepcopy(first)
    second.update(id="two", batch_id="other")
    third = project(item("verifying", id="three", game_id=2))
    result = metrics([first, second, third])
    assert (result["total"], result["operations"], result["completed"], result["active"]) == (2, 3, 1, 1)
    assert result["progress"]["kind"] == "indeterminate"
    assert len(result["current"]) == 1
    assert metrics([], [{"status": "scanning", "control": "run"}])["progress"]["kind"] == "indeterminate"


def test_companion_audio_and_failed_cue_fold_without_discarding_history():
    cue = project(
        item(
            "awaiting_decision",
            identification={"reason": "ISO9660 immagine incompleta"},
            source_key="C:/input/Game.cue",
        )
    )
    track = project(item("awaiting_decision", id="track", source_key="C:/input/Game (Track 1).bin"))
    result = cards([cue, track])
    assert len(result) == 1 and result[0]["experience"]["state"] == "blocked"
    assert len(result[0]["operation_ids"]) == 2 and len(result[0]["companions"]) == 1


def test_sections_filter_before_pagination_and_resume_old_jobs(setup):
    _, client, source, _, _ = setup
    batch = create(client, [nes(source / "One.nes")])
    ready = client.get(f"/api/installations/{batch['id']}?section=attention&page_size=1").json()
    assert ready["card_total"] == 1 and ready["cards"][0]["experience"]["code"] == "confirmation"
    confirm(client, batch)
    finished(client, batch)
    active = client.get(f"/api/installations/{batch['id']}?section=active").json()
    assert not active["cards"] and active["card_total"] == 0
    done = client.get(f"/api/installations/{batch['id']}?section=completed").json()
    assert done["cards"][0]["experience"]["files_verified"]
    overview = client.get("/api/installations").json()["experience_summary"]
    assert overview["total"] == overview["completed"] == 1


def test_metadata_review_persists_without_modifying_files(setup):
    _, client, source, remote, _ = setup
    batch = create(client, [nes(source / "One.nes")])
    confirm(client, batch)
    result = finished(client, batch)
    entry = result["items"][0]
    writes = remote.sftp.writes
    response = client.post(
        f"/api/installations/items/{entry['id']}/visible", json={"confirmed": True, "metadata_review": True}
    )
    assert response.status_code == 200
    current = client.get(f"/api/installations/{batch['id']}").json()["cards"][0]
    assert current["experience"]["state"] == "console_update"
    assert current["experience"]["visibility"] == "operator_confirmed"
    assert remote.sftp.writes == writes


def test_gamelist_conflict_regenerates_once_without_overwrite(setup):
    app, client, source, remote, _ = setup
    from sqlalchemy import select

    from backend.db import InstallationBatch, InstallationItem, SyncRun

    batch = create(client, [nes(source / "One.nes")])
    confirm(client, batch)
    finished(client, batch)
    app.state.installations.shutdown()
    with app.state.sessions.begin() as db:
        row = db.scalar(select(InstallationItem).where(InstallationItem.batch_id == batch["id"]))
        run = db.get(SyncRun, row.sync_run_id)
        db.get(InstallationBatch, batch["id"]).status = "running"
        row.status = "transferring"
        run.status, run.error = "failed", "Gamelist cambiato dopo il dry-run: preparare una nuova anteprima"
        item_id, old_run = row.id, run.id
    writes = remote.sftp.writes
    app.state.installations.stop.clear()
    app.state.installations.tick()
    current = client.get(f"/api/installations/{batch['id']}").json()["items"][0]
    assert current["sync_run_id"] == "" and current["progress"]["metadata_replans"] == 1
    assert current["progress"]["superseded_plans"] == [old_run]
    assert remote.sftp.writes == writes
    # Repeated conflict is left for a conscious user action; not an infinite retry loop.
    with app.state.sessions.begin() as db:
        row = db.get(InstallationItem, item_id)
        row.sync_run_id, row.status = old_run, "transferring"
    app.state.installations.tick()
    current = client.get(f"/api/installations/{batch['id']}").json()["items"][0]
    assert current["status"] == "failed" and current["progress"]["metadata_replans"] == 1


def test_metadata_only_second_pass_is_not_a_reinstallation_or_existing_copy():
    value = item(
        "installed",
        progress={
            "report": {"games": [{"status": "present"}]},
            "reports": [{"games": [{"status": "transferred"}]}, {"games": [{"status": "present"}]}],
        },
    )
    assert project(value)["experience"]["state"] == "installed"


def test_repeated_unidentified_archive_uses_content_evidence_not_title_similarity():
    value = item(
        "failed",
        identification={"title": "Uncertain", "archive": {"sha256": "same"}},
        source_key="C:/batch1/Disc.cue",
    )
    first = project(value)
    second = project({**value, "id": "two", "source_key": "C:/batch2/Disc.cue"})
    result = metrics([first, second])
    assert result["operations"] == 2 and result["total"] == 1 and result["identified"] == 0


def test_failed_sync_can_have_verified_game_files_and_unfinished_metadata():
    value = item("failed", game_id=1, error={"cause": "Gamelist cambiato dopo il dry-run"})
    result = view(
        value,
        {"control": "run", "authorized": True},
        {"status": "failed", "report": {"games": [{"status": "transferred"}]}},
    )
    assert result["files_verified"] and result["state"] == "console_update"
    assert result["code"] == "metadata_changed" and "retry" in result["actions"]


def test_same_cached_cue_in_different_jobs_counts_two_operations_one_copy():
    first = project(item("ready", game_id=1, source_key="C:/cache/files/Game.cue"))
    second = project(
        item("ready", id="two", game_id=1, batch_id="other", source_key="C:/cache/files/Game.cue")
    )
    result = metrics([first, second])
    assert result["operations"] == 2 and result["total"] == 1


def test_same_member_basename_in_distinct_archive_folders_is_not_merged():
    first = project(
        item(
            "failed",
            identification={"archive": {"sha256": "archive"}},
            source_key="C:/cache/files/A/Game.cue",
        )
    )
    second = project(
        item(
            "failed",
            id="two",
            identification={"archive": {"sha256": "archive"}},
            source_key="C:/cache/files/B/Game.cue",
        )
    )
    assert metrics([first, second])["total"] == 2
