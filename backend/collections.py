"""Owned collections are distinct from a metadata-only wishlist of classics."""

import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, insert, select

from backend.acquisition import fingerprint, record
from backend.collection_schemas import CurationInput, MetadataReviewInput
from backend.config import PROJECT
from backend.db import (
    ArcadeValidation,
    CatalogEntry,
    CatalogSource,
    EssentialClassic,
    Game,
    GameCuration,
    GameInsight,
    SyncPresence,
)
from backend.paths import digest


def metadata_fingerprint(game, insight=None):
    return fingerprint(
        {
            **{
                key: getattr(game, key)
                for key in (
                    "title",
                    "platform",
                    "genre",
                    "year",
                    "author",
                    "publisher",
                    "description",
                    "cover_path",
                    "sha256",
                )
            },
            "screenshot_path": insight.screenshot_path if insight else "",
        }
    )


def present(game):
    return bool(game.files) and all(Path(f["path"]).is_file() for f in game.files)


def identified(game, curation):
    return bool(curation and curation.classic_id and curation.matched_sha == game.sha256)


def member(game, curation):
    return bool(
        present(game)
        and curation
        and curation.mode != "exclude"
        and (curation.mode == "include" or identified(game, curation))
    )


class Collections:
    def __init__(self, sessions, intelligence, lock):
        self.sessions = sessions
        self.intelligence = intelligence
        self.lock = lock
        self.router = self.routes()

    def start(self):
        raw = (PROJECT / "backend/resources/essential_classics.json").read_bytes()
        payload = json.loads(raw)
        revision = hashlib.sha256(raw).hexdigest()
        with self.sessions.begin() as db:
            first = db.scalar(select(EssentialClassic).limit(1))
            if first and first.details.get("catalog_revision") == revision:
                return
            rows = []
            for item in payload["entries"]:
                values = dict(
                    id=item["id"],
                    title=item["title"],
                    platform=item["platform"],
                    genre=item.get("genre") or "",
                    year=item.get("year"),
                    details={**item, "catalog_revision": revision},
                )
                if first:
                    db.merge(EssentialClassic(**values))
                else:
                    rows.append(values)
            if rows:
                db.execute(insert(EssentialClassic), rows)

    def snapshot(self):
        with self.sessions() as db:
            games = list(db.scalars(select(Game).order_by(Game.id)))
            curations = {x.game_id: x for x in db.scalars(select(GameCuration))}
            insights = {x.game_id: x for x in db.scalars(select(GameInsight))}
            validations = {x.game_id: x for x in db.scalars(select(ArcadeValidation))}
            synced = {(x.game_id, x.sha256) for x in db.scalars(select(SyncPresence))}
        return games, curations, insights, validations, synced

    def prepare_sync(self, games, options):
        with self.sessions() as db:
            curations = {x.game_id: x for x in db.scalars(select(GameCuration))}
            insights = {x.game_id: x for x in db.scalars(select(GameInsight))}
            if options.collection:
                required = {g.id for g in db.scalars(select(Game)) if member(g, curations.get(g.id))}
                if not required.issubset({g.id for g in games}):
                    raise ValueError("Per sincronizzare la raccolta selezionare tutti i suoi giochi presenti")
            for game in games:
                curation = curations.get(game.id)
                insight = insights.get(game.id)
                game._rlm_classic = member(game, curation)
                game._rlm_position = curation.position if curation else 0
                game._rlm_screenshot = insight.screenshot_path if insight else ""
        return fingerprint(
            [
                {
                    "id": g.id,
                    "metadata": metadata_fingerprint(g),
                    "favorite": g.favorite,
                    "classic": g._rlm_classic,
                    "position": g._rlm_position,
                    "screenshot": g._rlm_screenshot,
                }
                for g in sorted(games, key=lambda g: g.id)
            ]
        )

    def owned(self):
        games, curations, insights, validations, synced = self.snapshot()
        result = []
        for game in games:
            curation = curations.get(game.id)
            insight = insights.get(game.id)
            validation = validations.get(game.id)
            current_validation = validation and validation.archive_sha == game.sha256
            status = curation.metadata_status if curation else "unverified"
            if (
                curation
                and status == "verified"
                and curation.metadata_fingerprint != metadata_fingerprint(game, insight)
            ):
                status = "review"
            screenshot = bool(insight and insight.screenshot_path and Path(insight.screenshot_path).is_file())
            value = record(game)
            value.update(
                classic_id=curation.classic_id if identified(game, curation) else None,
                in_classics=member(game, curation),
                membership=curation.mode if curation else "auto",
                position=curation.position if curation else 0,
                availability="present" if present(game) else "missing_file",
                compatibility=("validated_set" if validation.status == "complete" else "incomplete")
                if current_validation
                else "unverified",
                synchronized=(game.id, game.sha256) in synced,
                test_status=insight.test_status
                if insight and insight.test_evidence.get("sha256") == game.sha256
                else "untested",
                metadata_status=status,
                metadata_note=curation.metadata_note if curation else "",
                cover_available=bool(game.cover_path and Path(game.cover_path).is_file()),
                screenshot_available=screenshot,
            )
            result.append(value)
        return result

    def match(self, run_id):
        with self.sessions() as db:
            classics = list(db.scalars(select(EssentialClassic)))
            games = list(db.scalars(select(Game)))
            validations = {x.game_id: x for x in db.scalars(select(ArcadeValidation))}
            entries = {
                x.uid: x
                for x in db.scalars(
                    select(CatalogEntry)
                    .join(CatalogSource, CatalogSource.active_run == CatalogEntry.run_id)
                    .where(CatalogEntry.uid.in_([v.catalog_uid for v in validations.values()]))
                )
            }
            source_hashes = {x.id: x.sha256 for x in db.scalars(select(CatalogSource))}
        by_uid: dict[str, set[str]] = {}
        by_sha: dict[tuple[str, str], set[str]] = {}
        for classic in classics:
            for identity in classic.details["identifiers"]:
                if identity.get("catalog_uid"):
                    by_uid.setdefault(identity["catalog_uid"], set()).add(classic.id)
                for file in identity.get("hashes", []):
                    if file.get("sha1"):
                        by_sha.setdefault((classic.platform, file["sha1"].lower()), set()).add(classic.id)
        matched, unresolved = [], []
        for index, game in enumerate(games):
            self.intelligence.checkpoint(run_id, {"done": index, "total": len(games)})
            found: set[str] = set()
            basis = ""
            if not present(game):
                unresolved.append({"game_id": game.id, "reason": "File locale mancante"})
                continue
            validation = validations.get(game.id)
            if (
                validation
                and validation.status == "complete"
                and validation.archive_sha == game.sha256
                and digest(Path(game.local_path)) == game.sha256
            ):
                entry = entries.get(validation.catalog_uid)
                if entry and source_hashes.get(entry.source_id) == validation.source_sha:
                    found = by_uid.get(entry.uid, set())
                    basis = "DAT e archivio verificati"
            elif len(game.files) == 1 and game.platform not in {
                "arcade",
                "mame-libretro",
                "fba",
                "neogeo",
                "psx",
            }:
                sha1 = hashlib.sha1()
                sha256 = hashlib.sha256()
                with Path(game.files[0]["path"]).open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        sha1.update(block)
                        sha256.update(block)
                if sha256.hexdigest() == game.sha256:
                    found = by_sha.get((game.platform, sha1.hexdigest()), set())
                    basis = "SHA-1 DAT e SHA-256 locale verificati"
            with self.lock, self.sessions.begin() as db:
                current = db.get(Game, game.id)
                if not current or current.sha256 != game.sha256:
                    continue
                row = db.get(GameCuration, game.id) or GameCuration(game_id=game.id)
                if row.match_basis == "Identità confermata dall'utente":
                    continue
                row.classic_id = next(iter(found)) if len(found) == 1 else ""
                row.matched_sha = game.sha256 if len(found) == 1 else ""
                row.match_basis = basis if len(found) == 1 else ""
                db.add(row)
            if len(found) == 1:
                matched.append({"game_id": game.id, "classic_id": next(iter(found)), "basis": basis})
            else:
                unresolved.append(
                    {
                        "game_id": game.id,
                        "reason": "Identità ambigua"
                        if found
                        else "Nessun identificativo affidabile; revisione manuale possibile",
                    }
                )
        return {"matched": matched, "unresolved": unresolved}

    def routes(self):
        router = APIRouter(prefix="/api/collections")

        @router.get("/summary")
        def summary():
            owned = self.owned()
            present_ids = {
                x["classic_id"] for x in owned if x["classic_id"] and x["availability"] == "present"
            }
            with self.sessions() as db:
                total = db.scalar(select(func.count()).select_from(EssentialClassic))
            fields = {
                field: sum(bool(x[field]) for x in owned)
                for field in [
                    "title",
                    "genre",
                    "year",
                    "author",
                    "publisher",
                    "description",
                    "cover_available",
                    "screenshot_available",
                ]
            }
            return {
                "catalogued": total,
                "present_classics": len(present_ids),
                "missing_classics": total - len(present_ids),
                "collection_games": sum(x["in_classics"] for x in owned),
                "games": len(owned),
                "covers": fields["cover_available"],
                "screenshots": fields["screenshot_available"],
                "fields": {
                    key: {"count": value, "percent": round(value * 100 / len(owned), 1) if owned else 0}
                    for key, value in fields.items()
                },
                "review_needed": sum(
                    x["metadata_status"] != "verified" or any(not x[k] for k in fields) for x in owned
                ),
            }

        @router.get("/owned")
        def owned(
            q: str = Query("", max_length=300),
            platform: str = "",
            genre: str = "",
            view: str = "all",
            availability: str = "",
            compatibility: str = "",
            synced: str = "",
            test_status: str = "",
            metadata_status: str = "",
            favorite: bool = False,
            sort: str = "title",
            page: int = Query(1, ge=1),
            page_size: int = Query(36, ge=1, le=100),
        ):
            values = [
                x
                for x in self.owned()
                if (not q or q.casefold() in x["title"].casefold())
                and (not platform or x["platform"] == platform)
                and (not genre or genre.casefold() in x["genre"].casefold())
                and (view != "classics" or x["in_classics"])
                and (not favorite or x["favorite"])
                and (not availability or x["availability"] == availability)
                and (not compatibility or x["compatibility"] == compatibility)
                and (not synced or x["synchronized"] == (synced == "yes"))
                and (not test_status or x["test_status"] == test_status)
                and (not metadata_status or x["metadata_status"] == metadata_status)
            ]
            keys = {
                "title": lambda x: (x["title"].casefold(), x["id"]),
                "year": lambda x: (x["year"] or 9999, x["title"]),
                "manual": lambda x: (x["position"], x["title"]),
                "favorites": lambda x: (not x["favorite"], x["title"]),
            }
            if sort not in keys:
                raise ValueError("Ordinamento non valido")
            values.sort(key=keys[sort])
            return {"items": values[(page - 1) * page_size : page * page_size], "total": len(values)}

        @router.get("/classics")
        def classics(
            q: str = Query("", max_length=300),
            platform: str = "",
            missing: bool = True,
            page: int = Query(1, ge=1),
            page_size: int = Query(36, ge=1, le=100),
        ):
            owned_ids = {
                x["classic_id"] for x in self.owned() if x["classic_id"] and x["availability"] == "present"
            }
            with self.sessions() as db:
                query = select(EssentialClassic).order_by(EssentialClassic.title, EssentialClassic.id)
                if q:
                    query = query.where(EssentialClassic.title.icontains(q, autoescape=True))
                if platform:
                    query = query.where(EssentialClassic.platform == platform)
                if missing and owned_ids:
                    query = query.where(EssentialClassic.id.not_in(owned_ids))
                total = db.scalar(select(func.count()).select_from(query.subquery()))
                rows = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)))
                return {
                    "total": total,
                    "items": [
                        {
                            **record(x),
                            "present": x.id in owned_ids,
                            "compatibility": "Da verificare sulla copia e sul core installato",
                        }
                        for x in rows
                    ],
                }

        @router.post("/match", status_code=202)
        def match():
            return self.intelligence.queue("classics_match", self.match)

        @router.put("/games/{game_id}")
        def curate(game_id: int, body: CurationInput):
            with self.lock, self.sessions.begin() as db:
                game = db.get(Game, game_id)
                if not game:
                    raise HTTPException(404, "Gioco non trovato")
                row = db.get(GameCuration, game_id) or GameCuration(game_id=game_id)
                if body.classic_id is not None:
                    classic = db.get(EssentialClassic, body.classic_id) if body.classic_id else None
                    if body.classic_id and (not classic or not body.identity_confirmed):
                        raise ValueError("Confermare esplicitamente l'identità del classico selezionato")
                    arcade = {"arcade", "mame-libretro", "fba", "neogeo"}
                    if (
                        classic
                        and classic.platform != game.platform
                        and not ({classic.platform, game.platform} <= arcade)
                    ):
                        raise ValueError("Piattaforma del classico diversa dalla copia locale")
                    row.classic_id = body.classic_id
                    row.matched_sha = game.sha256 if body.classic_id else ""
                    row.match_basis = "Identità confermata dall'utente" if body.classic_id else ""
                row.mode = body.mode
                row.position = body.position
                db.add(row)
            return {"ok": True}

        @router.put("/games/{game_id}/review")
        def review(game_id: int, body: MetadataReviewInput):
            if body.status == "verified" and len(body.note) < 12:
                raise ValueError("Indicare fonte o prova della verifica dei metadati")
            with self.lock, self.sessions.begin() as db:
                game = db.get(Game, game_id)
                if not game:
                    raise HTTPException(404, "Gioco non trovato")
                row = db.get(GameCuration, game_id) or GameCuration(game_id=game_id)
                row.metadata_status = body.status
                row.metadata_note = body.note
                row.metadata_fingerprint = metadata_fingerprint(game, db.get(GameInsight, game.id))
                db.add(row)
            return {"ok": True}

        return router
