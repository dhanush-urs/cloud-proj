import logging
import os

from app.db.base import Base
from app.db.session import engine

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Initialize database.

    In PRODUCTION (APP_ENV=production):
        - Does NOT call create_all(). Schema is managed only by Alembic.
        - Validates DB is reachable with a light probe.

    In DEVELOPMENT / TEST:
        - Calls create_all() for convenience so a fresh local DB works without
          requiring migrations to be applied manually.
    """
    app_env = os.getenv("APP_ENV", "development").lower()

    if app_env == "production":
        # Production: schema managed by Alembic only. Do NOT mutate schema.
        logger.info("Production mode: skipping create_all() — Alembic manages schema.")
        return

    # Development / test: auto-create tables for convenience
    logger.info(f"Dev/test mode (APP_ENV={app_env}): running create_all() for local convenience.")
    Base.metadata.create_all(bind=engine)