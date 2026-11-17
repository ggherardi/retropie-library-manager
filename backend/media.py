"""Identity-bound media previews, authorized downloads and explicit manual corrections."""

import hashlib
import io
import json
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy import select

from backend.acquisition import fingerprint, record
from backend.acquisition_schemas import EnrichInput
from backend.collection_schemas import LocalMediaInput, MediaApplyInput, MediaPreviewInput
from backend.config import PROJECT
from backend.db import DiscoveryEntry, Game, GameInsight, MediaAsset, MediaPlan
from backend.discovery_sources import LICENSES
from backend.paths import allowed, digest

MEDIA_LICENSES = LICENSES | {"Artistic-2.0", "CC-BY-NC-SA-3.0"}


class MediaService:
    def __init__(self, sessions, data_dir, acquisition, intelligence, lock):
        self.sessions, self.data_dir = sessions, data_dir
        self.acquisition, self.intelligence, self.lock = acquisition, intelligence, lock
        entries = json.loads((PROJECT / "backend/resources/reviewed_media.json").read_text(encoding="utf-8"))[
            "entries"
        ]
        self.reviewed = {x["game_sha256"]: x["assets"] for x in entries}
        self.router = self.routes()

    def cache(self, asset):
        if asset.get("license") not in MEDIA_LICENSES or not asset.get("git_blob_sha1"):
            raise ValueError("Media senza licenza e integrità verificabili")
        key = fingerprint(asset)
        folder = self.data_dir / "media"
        folder.mkdir(exist_ok=True)
        target = folder / (key + ".png")
        receipt = folder / (key + ".json")
        if target.is_file() and receipt.is_file():
            evidence = json.loads(receipt.read_text(encoding="utf-8"))
            if digest(target) == evidence["sha256"]:
                return target
            raise ValueError("Cache media modificata: revisione richiesta")
        if asset.get("notice_git_blob_sha1"):
            notice = self.acquisition.http.read(asset["source_url"], 1_000_000)
            if (
                hashlib.sha1(f"blob {len(notice)}\0".encode() + notice).hexdigest()
                != asset["notice_git_blob_sha1"]
            ):
                raise ValueError("Dichiarazione dei diritti differente da quella verificata")
        content = self.acquisition.http.read(asset["url"], 8_000_000)
        if hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest() != asset["git_blob_sha1"]:
            raise ValueError("Hash media non corrispondente alla fonte")
        self.store_png(content, target)
        receipt.write_text(
            json.dumps({"sha256": digest(target), "source": asset}, ensure_ascii=False), encoding="utf-8"
        )
        return target

    @staticmethod
    def store_png(content, target):
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP", "GIF"} or image.width * image.height > 20_000_000:
                raise ValueError("Immagine non supportata o troppo grande")
            image.load()
            temporary = target.with_name(str(uuid4()) + ".png")
            try:
                image.convert("RGBA").save(temporary, format="PNG")
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)

    def preview(self, body, run_id):
        enriched = self.acquisition.enrich(EnrichInput(game_ids=body.game_ids, apply=False, covers=False))
        candidates = []
        with self.sessions() as db:
            for match in enriched["matches"]:
                game = db.get(Game, match["game_id"])
                entry = db.get(DiscoveryEntry, match["entry_id"])
                insight = db.get(GameInsight, game.id)
                assets = list(entry.payload.get("media", []))
                if not assets and entry.payload.get("cover"):
                    assets = [{**entry.payload["cover"], "kind": "cover", "source_url": entry.source_url}]
                assets.extend(self.reviewed.get(game.sha256, []))
                chosen: set[str] = set()
                for asset in assets:
                    kind = asset.get("kind")
                    if (
                        kind not in {"cover", "screenshot"}
                        or asset.get("license") not in MEDIA_LICENSES
                        or not asset.get("git_blob_sha1")
                    ):
                        continue
                    previous = (
                        game.cover_path if kind == "cover" else insight.screenshot_path if insight else ""
                    )
                    if previous and not body.replace_existing:
                        continue
                    candidates.append(
                        {
                            "id": str(uuid4()),
                            "game_id": game.id,
                            "title": game.title,
                            "kind": kind,
                            "game_sha": game.sha256,
                            "entry_id": entry.id,
                            "entry_fingerprint": fingerprint(record(entry)),
                            "asset": asset,
                            "previous_path": previous,
                            "recommended": kind not in chosen,
                            "match_basis": "Hash del file verificato dal provider",
                        }
                    )
                    chosen.add(kind)
        plan_id = str(uuid4())
        payload = {
            "candidates": candidates,
            "unresolved": enriched["unresolved"],
            "replace_existing": body.replace_existing,
        }
        with self.sessions.begin() as db:
            db.add(MediaPlan(id=plan_id, payload=payload))
        return {"id": plan_id, **payload}

    def assign(self, db, game, kind, path, evidence):
        for previous in db.scalars(
            select(MediaAsset).where(
                MediaAsset.game_id == game.id, MediaAsset.kind == kind, MediaAsset.active.is_(True)
            )
        ):
            previous.active = False
        asset = MediaAsset(
            id=str(uuid4()),
            game_id=game.id,
            kind=kind,
            path=str(path),
            sha256=digest(path),
            evidence=evidence,
        )
        db.add(asset)
        if kind == "cover":
            game.cover_path = str(path)
        else:
            insight = db.get(GameInsight, game.id) or GameInsight(game_id=game.id)
            insight.screenshot_path = str(path)
            db.add(insight)
        return asset.id

    def apply(self, plan_id, body, run_id):
        with self.sessions() as db:
            plan = db.get(MediaPlan, plan_id)
            if not plan:
                raise ValueError("Anteprima media non trovata")
            if plan.status == "applied":
                return plan.result
            selected = [x for x in plan.payload["candidates"] if x["id"] in body.candidate_ids]
        if len(selected) != len(set(body.candidate_ids)):
            raise ValueError("Selezione estranea all'anteprima")
        keys = [(x["game_id"], x["kind"]) for x in selected]
        if len(keys) != len(set(keys)):
            raise ValueError("Selezionare una sola immagine per gioco e tipo")
        applied, failed = [], []
        for index, candidate in enumerate(selected):
            self.intelligence.checkpoint(run_id, {"done": index, "total": len(selected)})
            try:
                with self.sessions() as db:
                    entry = db.get(DiscoveryEntry, candidate["entry_id"])
                    if not entry or fingerprint(record(entry)) != candidate["entry_fingerprint"]:
                        raise ValueError("Fonte cambiata dopo l'anteprima")
                    game = db.get(Game, candidate["game_id"])
                    if (
                        not game
                        or game.sha256 != candidate["game_sha"]
                        or digest(Path(game.local_path)) != candidate["game_sha"]
                    ):
                        raise ValueError("Gioco modificato dopo l'anteprima")
                path = self.cache(candidate["asset"])
                with self.lock, self.sessions.begin() as db:
                    game = db.get(Game, candidate["game_id"])
                    insight = db.get(GameInsight, game.id)
                    previous = (
                        game.cover_path
                        if candidate["kind"] == "cover"
                        else insight.screenshot_path
                        if insight
                        else ""
                    )
                    if previous != candidate["previous_path"] or game.sha256 != candidate["game_sha"]:
                        raise ValueError("Associazione modificata dopo l'anteprima")
                    asset_id = self.assign(
                        db,
                        game,
                        candidate["kind"],
                        path,
                        {
                            **candidate["asset"],
                            "match_basis": candidate["match_basis"],
                            "game_sha": game.sha256,
                        },
                    )
                applied.append({"game_id": game.id, "kind": candidate["kind"], "asset_id": asset_id})
            except (ValueError, OSError, httpx.HTTPError, Image.DecompressionBombError) as exc:
                failed.append({"game_id": candidate["game_id"], "kind": candidate["kind"], "error": str(exc)})
        result = {"applied": applied, "failed": failed}
        with self.sessions.begin() as db:
            plan = db.get(MediaPlan, plan_id)
            plan.status, plan.result = "applied", result
        return result

    def routes(self):
        router = APIRouter(prefix="/api/media")

        @router.post("/plans", status_code=202)
        def preview(body: MediaPreviewInput):
            return self.intelligence.queue("media_preview", lambda run: self.preview(body, run))

        @router.get("/plans/{plan_id}")
        def get_plan(plan_id: str):
            with self.sessions() as db:
                plan = db.get(MediaPlan, plan_id)
                if not plan:
                    raise HTTPException(404, "Anteprima non trovata")
                return record(plan)

        @router.get("/plans/{plan_id}/candidates/{candidate_id}/image")
        def preview_image(plan_id: str, candidate_id: str):
            with self.sessions() as db:
                plan = db.get(MediaPlan, plan_id)
                candidate = (
                    next((x for x in plan.payload["candidates"] if x["id"] == candidate_id), None)
                    if plan
                    else None
                )
            if not candidate:
                raise HTTPException(404, "Immagine non trovata")
            return FileResponse(self.cache(candidate["asset"]), media_type="image/png")

        @router.post("/plans/{plan_id}/confirm", status_code=202)
        def confirm(plan_id: str, body: MediaApplyInput):
            return self.intelligence.queue("media_apply", lambda run: self.apply(plan_id, body, run))

        @router.get("/games/{game_id}/history")
        def history(game_id: int):
            with self.sessions() as db:
                return [
                    record(x)
                    for x in db.scalars(
                        select(MediaAsset)
                        .where(MediaAsset.game_id == game_id)
                        .order_by(MediaAsset.created_at.desc())
                    )
                ]

        @router.get("/games/{game_id}/{kind}")
        def image(game_id: int, kind: str):
            with self.sessions() as db:
                game = db.get(Game, game_id)
                insight = db.get(GameInsight, game_id)
                path = (
                    game.cover_path
                    if game and kind == "cover"
                    else insight.screenshot_path
                    if insight and kind == "screenshot"
                    else ""
                )
            if not path:
                raise HTTPException(404, "Media assente")
            return FileResponse(allowed(path, [*self.intelligence.roots(), str(self.data_dir)]))

        @router.post("/games/{game_id}/local")
        def local(game_id: int, body: LocalMediaInput):
            path = allowed(body.path, self.intelligence.roots())
            if path.stat().st_size > 8_000_000:
                raise ValueError("Immagine oltre 8 MB")
            content = path.read_bytes()
            folder = self.data_dir / "media"
            folder.mkdir(exist_ok=True)
            target = folder / (hashlib.sha256(content).hexdigest() + ".png")
            self.store_png(content, target)
            with self.lock, self.sessions.begin() as db:
                game = db.get(Game, game_id)
                if not game:
                    raise HTTPException(404, "Gioco non trovato")
                asset_id = self.assign(
                    db,
                    game,
                    body.kind,
                    target,
                    {
                        "source_url": body.source,
                        "license": body.license,
                        "match_basis": "Identità e diritti confermati dall'utente",
                        "game_sha": game.sha256,
                    },
                )
            return {"id": asset_id}

        return router
