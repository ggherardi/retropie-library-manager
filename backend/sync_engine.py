"""Verified manifests, atomic game groups and conservative EmulationStation updates."""

import base64
import hashlib
import posixpath
from pathlib import Path
from typing import Any

from backend.exports import prepare_games
from backend.gamelist import merge_gamelist
from backend.paths import digest, local_path
from backend.remote_fs import SafeRemote, binary_source, diagnostics
from backend.scanner import linked_files


def encoded_file(path, content, kind):
    return {
        "path": path,
        "content": base64.b64encode(content).decode(),
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "kind": kind,
    }


def remote_for(connection, config, diag):
    return SafeRemote(connection, [config["rom_root"], diag["es_root"], "/etc/emulationstation/gamelists"])


def build_plan(connection, config, games, options):
    diag = diagnostics(connection, config)
    remote = remote_for(connection, config, diag)
    remote.path(config["rom_root"])
    manifest, copies, generated = prepare_games(games, stable=True)
    sources = {target: str(source) for source, target, _ in copies}
    group_plans = []
    media = {}
    xml_games: dict[str, list[dict]] = {}
    warnings = []
    blocked = []
    by_id = {g.id: g for g in games}
    for entry in manifest["games"]:
        game = by_id[entry["id"]]
        system = diag["systems"].get(game.platform)
        system_root = config["rom_root"] + "/" + game.platform
        if not system or posixpath.normpath(system["path"]) != system_root:
            blocked.append(f"{game.title}: directory console diversa dalla configurazione EmulationStation")
            continue
        launch = entry["launch"].split("/", 1)[1]
        if Path(launch).suffix.lower() not in system["extensions"]:
            blocked.append(f"{game.title}: formato di avvio non accettato da EmulationStation")
        if any(Path(f["path"]).suffix.lower() == ".chd" for f in game.files):
            if (
                not config["chd_confirmed"]
                or ".chd" not in system["extensions"]
                or not diag.get("psx_emulator_config")
            ):
                blocked.append(
                    f"{game.title}: verificare il supporto CHD del core PS1 e confermarlo nel dispositivo"
                )
        known = {str(local_path(f["path"])) for f in game.files}
        for file in game.files:
            source = local_path(file["path"])
            if source.suffix.lower() in {".cue", ".m3u"}:
                dependencies = linked_files(
                    source,
                    Path(
                        posixpath.commonpath(
                            [str(Path(f["path"]).parent).replace("\\", "/") for f in game.files]
                        )
                    ),
                )
                if any(str(p) not in known for p in dependencies):
                    raise ValueError("Dipendenza PS1 assente dal manifest: " + game.title)
        # Every file in a game has the same stable group directory.
        folder = "/".join(entry["files"][0]["path"].split("/")[:2])
        final = config["rom_root"] + "/" + folder
        files = []
        for file in entry["files"]:
            files.append({**file, "source": sources[file["path"]], "kind": "rom"})
        for target, text in generated:
            if target.startswith(folder + "/"):
                files.append(encoded_file(target, text.encode(), "playlist"))
        counts = {"new": 0, "present": 0, "modified": 0}
        for file in files:
            file["relative"] = file["path"][len(folder) + 1 :]
            file["path"] = config["rom_root"] + "/" + file["path"]
            actual = remote.hash(file["path"])
            file["state"] = "new" if actual is None else "present" if actual == file["sha256"] else "modified"
            counts[file["state"]] += 1
        if counts["modified"] or (remote.info(final) and counts["new"]):
            blocked.append(f"{game.title}: gruppo remoto differente o incompleto; nessuna sovrascrittura")
        group_plans.append(
            {"id": game.id, "title": game.title, "path": final, "files": files, "counts": counts}
        )
        record = {
            key: getattr(game, key)
            for key in ("title", "author", "publisher", "description", "genre", "year", "favorite")
        }
        record["launch"] = launch
        if options.covers and game.cover_path:
            try:
                cover = local_path(game.cover_path)
                if (
                    cover.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}
                    or cover.stat().st_size > 20_000_000
                ):
                    raise ValueError("Formato o dimensione copertina non supportati")
                sha = digest(cover)
                relative = f".rlm-media/{sha}{cover.suffix.lower()}"
                path = system_root + "/" + relative
                actual = remote.hash(path)
                state = "new" if actual is None else "present" if actual == sha else "modified"
                if state == "modified":
                    blocked.append("Copertina remota modificata: " + path)
                media[path] = {
                    "path": path,
                    "source": str(cover),
                    "sha256": sha,
                    "size": cover.stat().st_size,
                    "state": state,
                    "kind": "cover",
                    "game_id": game.id,
                }
                record["image"] = "./" + relative
            except (OSError, ValueError) as exc:
                warnings.append(f"{game.title}: copertina omessa ({exc})")
        xml_games.setdefault(game.platform, []).append(record)
    lists = []
    if options.metadata:
        for platform, records in xml_games.items():
            system_root = config["rom_root"] + "/" + platform
            candidates = [
                system_root + "/gamelist.xml",
                diag["es_root"] + "/gamelists/" + platform + "/gamelist.xml",
                "/etc/emulationstation/gamelists/" + platform + "/gamelist.xml",
            ]
            existing = None
            read_path = None
            for path in candidates:
                content = remote.read(path)
                if content is not None:
                    existing = content
                    read_path = path
                    break
            target = read_path if read_path in candidates[:2] else candidates[1]
            content = merge_gamelist(existing, records, system_root)
            item = encoded_file(target, content, "gamelist")
            item.update(
                read_path=read_path,
                original_sha=hashlib.sha256(existing).hexdigest() if existing is not None else None,
                original_target_sha=remote.hash(target),
                state="present" if existing == content and read_path == target else "update",
                backup_bytes=len(existing or b""),
                references=records,
            )
            lists.append(item)
        if diag["es_running"] and any(item["state"] != "present" for item in lists):
            warnings.append(
                "EmulationStation in esecuzione: ROM e copertine trasferibili, gamelist rinviati finché viene chiusa dall’utente."
            )
    required = sum(f["size"] for g in group_plans for f in g["files"] if f["state"] == "new")
    required += sum(m["size"] for m in media.values() if m["state"] == "new")
    required += sum(m["size"] + m["backup_bytes"] for m in lists if m["state"] != "present")
    space = remote.space(config["rom_root"])
    if required + config["safety_bytes"] > space["free"]:
        blocked.append("Spazio remoto insufficiente considerando il margine di sicurezza")
    return {
        "config": config,
        "options": options.model_dump(),
        "diagnostics": diag,
        "groups": group_plans,
        "media": list(media.values()),
        "gamelists": lists,
        "required_bytes": required,
        "free_bytes": space["free"],
        "safety_bytes": config["safety_bytes"],
        "warnings": warnings,
        "blocked": blocked,
        "can_sync": not blocked,
        "manifest": manifest,
    }


class SyncCancelled(Exception):
    pass


def perform_sync(connection, plan, run_id, checkpoint):
    config = plan["config"]
    diag = diagnostics(connection, config)
    remote = remote_for(connection, config, diag)
    marker = ".rlm-stage-" + run_id
    report: dict[str, Any] = {
        "games": [],
        "media": [],
        "gamelists": [],
        "transferred_bytes": 0,
        "skipped_files": 0,
        "backups": [],
    }
    completed = 0
    stages = []

    def check_space(required, destination=None):
        free = remote.space(destination or config["rom_root"])["free"]
        if required + config["safety_bytes"] > free:
            raise ValueError("Spazio remoto insufficiente: trasferimento bloccato")

    def transfer(file, target):
        nonlocal completed
        check_space(file["size"], target)
        if file.get("source") and (
            Path(file["source"]).stat().st_size != file["size"]
            or digest(Path(file["source"])) != file["sha256"]
        ):
            raise ValueError("File locale modificato dopo il dry-run")
        with binary_source(file) as source:
            remote.upload(
                target,
                source,
                file["size"],
                file["sha256"],
                lambda received: checkpoint(
                    {
                        "file": file["path"],
                        "file_bytes": received,
                        "file_total": file["size"],
                        "bytes": completed + received,
                        "total": plan["required_bytes"],
                    }
                ),
            )
        completed += file["size"]
        report["transferred_bytes"] = completed

    try:
        check_space(plan["required_bytes"])
        for group in plan["groups"]:
            checkpoint({"file": group["title"], "bytes": completed, "total": plan["required_bytes"]})
            if remote.info(group["path"]):
                if not all(remote.hash(f["path"]) == f["sha256"] for f in group["files"]):
                    raise ValueError("Gruppo remoto cambiato dopo il dry-run: " + group["title"])
                report["skipped_files"] += len(group["files"])
                report["games"].append({"title": group["title"], "status": "present"})
                continue
            staging = posixpath.dirname(group["path"]) + "/" + marker + "-" + str(group["id"])
            stages.append(staging)
            remote.mkdir(staging)
            for file in group["files"]:
                target = staging + "/" + file["relative"]
                if remote.hash(target) == file["sha256"]:
                    report["skipped_files"] += 1
                    continue
                transfer(file, target)
            # Revalidate every dependency immediately before atomic publication.
            if not all(remote.hash(staging + "/" + f["relative"]) == f["sha256"] for f in group["files"]):
                raise ValueError("Verifica finale del gruppo PS1/ROM fallita")
            checkpoint({"file": group["title"], "bytes": completed, "total": plan["required_bytes"]})
            remote.rename_new(staging, group["path"])
            report["games"].append({"title": group["title"], "status": "transferred"})
            checkpoint(
                {
                    "file": group["title"],
                    "bytes": completed,
                    "total": plan["required_bytes"],
                    "report": report,
                }
            )
        for file in plan["media"]:
            actual = remote.hash(file["path"])
            if actual == file["sha256"]:
                report["skipped_files"] += 1
                continue
            if actual:
                raise ValueError("Copertina remota diversa; nessuna sovrascrittura")
            staging = posixpath.dirname(file["path"]) + "/" + marker + "-media"
            remote.mkdir(staging)
            stages.append(staging)
            temporary = staging + "/" + file["sha256"]
            transfer(file, temporary)
            remote.rename_new(temporary, file["path"])
            remote.remove_owned_tree(staging, marker)
            report["media"].append(file["path"])
        # Never ask EmulationStation to stop, restart or reload implicitly.
        current_diag = diagnostics(connection, config)
        for file in plan["gamelists"]:
            if remote.hash(file["path"]) == file["sha256"]:
                report["gamelists"].append({"path": file["path"], "status": "present"})
                continue
            if current_diag["es_running"]:
                report["gamelists"].append(
                    {"path": file["path"], "status": "deferred", "reason": "EmulationStation in esecuzione"}
                )
                continue
            if file["read_path"] and remote.hash(file["read_path"]) != file["original_sha"]:
                raise ValueError("Gamelist cambiato dopo il dry-run: preparare una nuova anteprima")
            if remote.hash(file["path"]) != file["original_target_sha"]:
                raise ValueError("Destinazione gamelist cambiata dopo il dry-run")
            check_space(file["size"] + file["backup_bytes"], file["path"])
            staging = posixpath.dirname(file["path"]) + "/" + marker + "-xml"
            remote.mkdir(staging)
            stages.append(staging)
            temporary = staging + "/gamelist.xml"
            transfer(file, temporary)
            if remote.info(file["path"]):
                backup = file["path"] + ".rlm-backup-" + run_id
                old = remote.read(file["path"])
                if remote.hash(backup) is None:
                    remote.write_new(backup, old)
                if remote.hash(backup) != file["original_target_sha"]:
                    raise ValueError("Backup gamelist non verificato")
                report["backups"].append(backup)
                if remote.hash(file["path"]) != file["original_target_sha"]:
                    raise ValueError("Gamelist modificato durante il backup")
                checkpoint({"file": file["path"], "bytes": completed, "total": plan["required_bytes"]})
                remote.sftp.posix_rename(remote.path(temporary), remote.path(file["path"]))
            else:
                remote.rename_new(temporary, file["path"])
            remote.remove_owned_tree(staging, marker)
            report["gamelists"].append({"path": file["path"], "status": "updated"})
        report["space_after"] = remote.space(config["rom_root"])
        report["metadata_deferred"] = any(m["status"] == "deferred" for m in report["gamelists"])
        return report
    except SyncCancelled:
        for staging in stages:
            remote.remove_owned_tree(staging, marker)
        raise
