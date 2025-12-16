from __future__ import annotations

import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

log = logging.getLogger("db")

# Render persistent disk path (your current setup)
DB_URL = os.getenv("DB_URL", "sqlite:////var/data/irrigation_v2.db")

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --------- SQLite schema self-heal (idempotent) ---------
def _is_sqlite() -> bool:
    return DB_URL.startswith("sqlite")


def _table_exists(conn, table_name: str) -> bool:
    if not _is_sqlite():
        return True
    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": table_name},
    ).fetchone()
    return row is not None


def _sqlite_columns(conn, table_name: str) -> set[str]:
    cols: set[str] = set()
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    for r in rows:
        # PRAGMA table_info returns (cid, name, type, notnull, dflt_value, pk)
        cols.add(str(r[1]))
    return cols


def ensure_sqlite_schema() -> None:
    """
    Render uses a persistent SQLite disk. SQLAlchemy create_all() won't add new columns.
    This function safely adds missing columns via ALTER TABLE (idempotent).
    """
    if not _is_sqlite():
        return

    with engine.begin() as conn:
        # If the schedules table doesn't exist yet, create_all() will create it later.
        if not _table_exists(conn, "schedules"):
            log.info("DB migrate: schedules table not present yet (will be created).")
            return

        cols = _sqlite_columns(conn, "schedules")

        # Add columns used by current models/scheduler logic
        migrations: list[tuple[str, str]] = [
            ("days_of_week", "ALTER TABLE schedules ADD COLUMN days_of_week TEXT DEFAULT '*'"),
            ("skip_if_moisture_over", "ALTER TABLE schedules ADD COLUMN skip_if_moisture_over REAL"),
            ("moisture_lookback_minutes", "ALTER TABLE schedules ADD COLUMN moisture_lookback_minutes INTEGER DEFAULT 120"),
            ("last_run_minute", "ALTER TABLE schedules ADD COLUMN last_run_minute TEXT"),
        ]

        for col, sql in migrations:
            if col not in cols:
                conn.execute(text(sql))
                log.info("DB migrate: added schedules.%s", col)

        log.info("DB migrate: schedules schema OK")
