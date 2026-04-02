from fastapi import APIRouter
from neo4j import GraphDatabase
from redis import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check():
    return {
        "status": "ok",
        "service": "repobrain-api",
    }


@router.get("/live")
def liveness_check():
    """Kubernetes-style liveness probe."""
    return {"status": "alive"}


@router.get("/ready")
def readiness_check():
    settings = get_settings()

    db_ok = False
    db_error = None

    redis_ok = False
    redis_error = None

    neo4j_ok = False
    neo4j_error = None

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_error = str(exc)

    try:
        redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        redis_ok = redis_client.ping()
    except Exception as exc:
        redis_error = str(exc)

    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        with driver.session() as session:
            session.run("RETURN 1").single()
        neo4j_ok = True
        driver.close()
    except Exception as exc:
        neo4j_error = str(exc)

    all_ok = db_ok and redis_ok and neo4j_ok

    return {
        "status": "ready" if all_ok else "degraded",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": {
            "ok": db_ok,
            "error": db_error,
        },
        "redis": {
            "ok": redis_ok,
            "error": redis_error,
        },
        "neo4j": {
            "ok": neo4j_ok,
            "error": neo4j_error,
        },
    }