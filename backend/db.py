from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from backend.config import DATA


class Base(DeclarativeBase):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc)


class Game(Base):
    __tablename__ = "games"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    author: Mapped[str] = mapped_column(String(500), default="")
    publisher: Mapped[str] = mapped_column(String(500), default="")
    platform: Mapped[str] = mapped_column(String(30), index=True)
    region: Mapped[str] = mapped_column(String(80), default="Sconosciuta")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    genre: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    cover_path: Mapped[str] = mapped_column(Text, default="")
    size: Mapped[int] = mapped_column(Integer)
    format: Mapped[str] = mapped_column(String(30))
    local_path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    provenance: Mapped[str] = mapped_column(Text, default="Importazione locale")
    license: Mapped[str] = mapped_column(Text, default="Da verificare")
    files: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CatalogSource(Base):
    __tablename__ = "catalog_sources"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    active_run: Mapped[str] = mapped_column(String(36), default="", index=True)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CatalogEntry(Base):
    __tablename__ = "catalog_entries"
    __table_args__ = (
        UniqueConstraint("run_id", "name"),
        Index("ix_catalog_page", "run_id", "platform", "title"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    source_id: Mapped[str] = mapped_column(String(80), index=True)
    uid: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    title: Mapped[str] = mapped_column(String(500))
    platform: Mapped[str] = mapped_column(String(30), index=True)
    system: Mapped[str] = mapped_column(String(100), default="", index=True)
    manufacturer: Mapped[str] = mapped_column(String(300), default="")
    year: Mapped[str] = mapped_column(String(20), default="")
    genre: Mapped[str] = mapped_column(String(120), default="", index=True)
    players: Mapped[int | None] = mapped_column(Integer, nullable=True)
    orientation: Mapped[str] = mapped_column(String(30), default="")
    controls: Mapped[str] = mapped_column(String(300), default="")
    parent: Mapped[str] = mapped_column(String(300), default="", index=True)
    family: Mapped[str] = mapped_column(String(300), index=True)
    romof: Mapped[str] = mapped_column(String(300), default="")
    kind: Mapped[str] = mapped_column(String(20), default="game", index=True)
    components: Mapped[list[dict]] = mapped_column(JSON, default=list)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    payload_sha: Mapped[str] = mapped_column(String(64))


class CatalogRun(Base):
    __tablename__ = "catalog_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    source_id: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class GameInsight(Base):
    __tablename__ = "game_insights"
    game_id: Mapped[int] = mapped_column(primary_key=True)
    catalog_uid: Mapped[str] = mapped_column(String(64), default="", index=True)
    preferred_core: Mapped[str] = mapped_column(String(100), default="")
    machine_mode: Mapped[str] = mapped_column(String(20), default="unknown")
    asset_kind: Mapped[str] = mapped_column(String(20), default="game")
    test_status: Mapped[str] = mapped_column(String(20), default="untested", index=True)
    test_evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    screenshot_path: Mapped[str] = mapped_column(Text, default="")


class ArcadeValidation(Base):
    __tablename__ = "arcade_validations"
    game_id: Mapped[int] = mapped_column(primary_key=True)
    catalog_uid: Mapped[str] = mapped_column(String(64), index=True)
    source_sha: Mapped[str] = mapped_column(String(64))
    archive_sha: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), index=True)
    report: Mapped[dict] = mapped_column(JSON)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CatalogPreference(Base):
    __tablename__ = "catalog_preferences"
    family_key: Mapped[str] = mapped_column(String(150), primary_key=True)
    preferred_uid: Mapped[str] = mapped_column(String(64))


class CoreBinding(Base):
    __tablename__ = "core_bindings"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(36), index=True)
    source_id: Mapped[str] = mapped_column(String(80))
    core: Mapped[str] = mapped_column(String(100))
    source_sha: Mapped[str] = mapped_column(String(64))
    binary_sha: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(300))
    evidence: Mapped[str] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SyncPresence(Base):
    __tablename__ = "sync_presence"
    __table_args__ = (UniqueConstraint("game_id", "device_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)
    device_id: Mapped[str] = mapped_column(String(36), index=True)
    sha256: Mapped[str] = mapped_column(String(64))
    run_id: Mapped[str] = mapped_column(String(36))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DiscoveryEntry(Base):
    __tablename__ = "discovery_entries"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(100), index=True)
    external_id: Mapped[str] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(String(300), index=True)
    platform: Mapped[str] = mapped_column(String(30), index=True)
    author: Mapped[str | None] = mapped_column(String(500), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    genre: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    source_url: Mapped[str] = mapped_column(Text)
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    downloadable: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProviderState(Base):
    __tablename__ = "provider_states"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="idle")
    message: Mapped[str] = mapped_column(Text, default="")
    count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DownloadTask(Base):
    __tablename__ = "download_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entry_id: Mapped[str] = mapped_column(String(64), index=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    received: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    retry_at: Mapped[float] = mapped_column(default=0.0)
    error: Mapped[str] = mapped_column(Text, default="")
    etag: Mapped[str] = mapped_column(Text, default="")
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    game_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DownloadPlan(Base):
    __tablename__ = "download_plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    tasks: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(100), default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="unknown")
    diagnostics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")


class SyncRun(Base):
    __tablename__ = "sync_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(30), default="preparing", index=True)
    plan: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    progress: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def make_engine(data_dir=DATA):
    data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{(data_dir / 'library.db').as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


def sessions(engine):
    return sessionmaker(engine, expire_on_commit=False)
