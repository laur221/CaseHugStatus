from __future__ import annotations

import logging
import os
from typing import Iterable

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from ..models.models import Base
from ..core.profile_store import ensure_profile_path

logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/casehugauto"


def _has_module(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


def _normalize_database_url(database_url: str | None) -> str | None:
    """Normalize PostgreSQL URL to the available SQLAlchemy driver.

    On Python 3.14, psycopg2 wheels are not broadly available, so we prefer
    psycopg v3 when a generic postgresql:// URL is provided.
    """
    if not database_url:
        return database_url

    has_psycopg = _has_module("psycopg")
    has_psycopg2 = _has_module("psycopg2")

    if database_url.startswith("postgresql+psycopg://") and not has_psycopg and has_psycopg2:
        return database_url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)

    if database_url.startswith("postgresql+psycopg2://") and not has_psycopg2 and has_psycopg:
        return database_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)

    if (
        database_url.startswith("postgresql://")
        and "+psycopg" not in database_url
        and "+psycopg2" not in database_url
    ):
        if has_psycopg:
            return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        if has_psycopg2:
            return database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return database_url


def _require_database_url(database_url: str | None) -> str:
    resolved = _normalize_database_url(database_url or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL)
    if not resolved:
        raise RuntimeError(
            "DATABASE_URL is required. CaseHugAuto supports PostgreSQL only."
        )
    if not resolved.startswith("postgresql"):
        raise RuntimeError(
            "Only PostgreSQL connection strings are supported for CaseHugAuto."
        )
    return resolved


def _create_postgres_engine(database_url: str | URL, *, autocommit: bool = False):
    engine_kwargs = {
        "poolclass": NullPool,
        "echo": False,
        "pool_pre_ping": True,
    }
    if autocommit:
        engine_kwargs["isolation_level"] = "AUTOCOMMIT"
    return create_engine(database_url, **engine_kwargs)


def _maintenance_databases(target_database: str) -> Iterable[str]:
    configured = os.getenv("POSTGRES_MAINTENANCE_DB", "").strip()
    seen: set[str] = set()
    for candidate in (configured, "postgres", "template1"):
        if candidate and candidate != target_database and candidate not in seen:
            seen.add(candidate)
            yield candidate


def ensure_database_exists(database_url: str | None = None) -> bool:
    """Create the target PostgreSQL database if it does not already exist."""
    normalized_url = _require_database_url(database_url)
    target_url = make_url(normalized_url)
    target_database = target_url.database

    if not target_database:
        raise RuntimeError("DATABASE_URL must include a PostgreSQL database name.")

    last_error: Exception | None = None

    for maintenance_db in _maintenance_databases(target_database):
        admin_engine = _create_postgres_engine(
            target_url.set(database=maintenance_db),
            autocommit=True,
        )
        try:
            with admin_engine.connect() as connection:
                exists = connection.execute(
                    text(
                        "SELECT 1 FROM pg_database WHERE datname = :database_name"
                    ),
                    {"database_name": target_database},
                ).scalar()
                if exists:
                    return False

                quoted_name = admin_engine.dialect.identifier_preparer.quote(
                    target_database
                )
                connection.exec_driver_sql(f"CREATE DATABASE {quoted_name}")
                logger.info("Created PostgreSQL database '%s'.", target_database)
                return True
        except OperationalError as exc:
            last_error = exc
            logger.warning(
                "Could not use maintenance database '%s' while ensuring '%s' exists: %s",
                maintenance_db,
                target_database,
                exc,
            )
        finally:
            admin_engine.dispose()

    if last_error:
        raise last_error

    raise RuntimeError(
        "Could not connect to a PostgreSQL maintenance database to create the target database."
    )


DATABASE_URL = _require_database_url(os.getenv("DATABASE_URL"))
engine = _create_postgres_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False)
SessionLocal.configure(bind=engine)


def configure_database(database_url: str | None = None) -> str:
    """Reconfigure the shared SQLAlchemy engine/session factory at runtime."""
    global DATABASE_URL, engine

    normalized_url = _require_database_url(database_url)
    ensure_database_exists(normalized_url)

    new_engine = _create_postgres_engine(normalized_url)
    with new_engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    old_engine = engine
    DATABASE_URL = normalized_url
    engine = new_engine
    SessionLocal.configure(bind=engine)
    os.environ["DATABASE_URL"] = normalized_url

    if old_engine is not new_engine:
        old_engine.dispose()

    logger.info("Using PostgreSQL database '%s'.", make_url(DATABASE_URL).database)
    return DATABASE_URL


def get_db():
    """Dependency injection pentru database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _sync_schema():
    """Apply lightweight schema patches for existing PostgreSQL databases."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "accounts" in tables:
        account_columns = {column["name"] for column in inspector.get_columns("accounts")}
        if "browser_profile_path" not in account_columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE accounts ADD COLUMN browser_profile_path VARCHAR(500)")
                )
            logger.info("Added accounts.browser_profile_path column.")


def _backfill_account_profile_paths():
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT id, account_name
                FROM accounts
                WHERE browser_profile_path IS NULL OR browser_profile_path = ''
                """
            )
        ).mappings()
        for row in rows:
            connection.execute(
                text(
                    """
                    UPDATE accounts
                    SET browser_profile_path = :browser_profile_path
                    WHERE id = :account_id
                    """
                ),
                {
                    "browser_profile_path": ensure_profile_path(row["account_name"]),
                    "account_id": row["id"],
                },
            )


def init_db(database_url: str | None = None):
    """Initialize PostgreSQL and create all application tables."""
    try:
        configure_database(database_url)
        Base.metadata.create_all(bind=engine)
        _sync_schema()
        _backfill_account_profile_paths()
        logger.info("[✓] Database initialized successfully")
        return True
    except Exception as e:
        logger.error("[✗] Database initialization failed: %s", e, exc_info=True)
        return False


def drop_db():
    """Drop all tables - USE WITH CAUTION"""
    Base.metadata.drop_all(bind=engine)
    print("[✓] Database dropped successfully")


class DatabaseConnection:
    """Context manager pentru database connections"""
    def __init__(self):
        self.session = None
    
    def __enter__(self) -> Session:
        self.session = SessionLocal()
        return self.session
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.close()
        return False
