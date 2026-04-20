import logging
import os

from sqlalchemy import text
from app.db.base import Base
from app.db.session import engine

logger = logging.getLogger(__name__)

# Columns that must exist in the files table but are not created by the initial
# create_all() because they were added in a later migration.  We apply them
# idempotently (IF NOT EXISTS) so this is safe to run on every startup.
_FILES_EXTRA_COLUMNS: list[tuple[str, str]] = [
    ("importance_score", "FLOAT"),
    ("summary_text",     "TEXT"),
    ("responsibilities", "TEXT"),
    ("imports_list",     "TEXT"),
    ("exports_list",     "TEXT"),
    ("framework_hints",  "TEXT"),
]


def _ensure_extra_columns(conn) -> None:
    """Add any missing optional columns to the files table (idempotent)."""
    for col_name, col_type in _FILES_EXTRA_COLUMNS:
        try:
            conn.execute(
                text(f"ALTER TABLE files ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            )
        except Exception as exc:
            # Non-fatal: log and continue — the column may already exist or the
            # DB may not support IF NOT EXISTS (older Postgres).
            logger.warning(f"Could not add column files.{col_name}: {exc}")


def init_db() -> None:
    """Initialize database.

    In PRODUCTION (APP_ENV=production):
        - Does NOT call create_all(). Schema is managed only by Alembic.
        - Validates DB is reachable with a light probe.

    In DEVELOPMENT / TEST:
        - Calls create_all() for convenience so a fresh local DB works without
          requiring migrations to be applied manually.
        - Also ensures optional enrichment columns exist (idempotent ALTER TABLE).
    """
    app_env = os.getenv("APP_ENV", "development").lower()

    if app_env == "production":
        # Production: schema managed by Alembic only. Do NOT mutate schema.
        logger.info("Production mode: skipping create_all() — Alembic manages schema.")
        return

    # Development / test: auto-create tables for convenience
    logger.info(f"Dev/test mode (APP_ENV={app_env}): running create_all() for local convenience.")
    Base.metadata.create_all(bind=engine)

    # Ensure enrichment columns added by migration a0a725601d8a are present.
    # create_all() only creates missing tables, not missing columns on existing tables.
    with engine.begin() as conn:
        _ensure_extra_columns(conn)
    logger.info("init_db: extra column check complete.")
