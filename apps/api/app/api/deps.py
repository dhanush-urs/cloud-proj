from typing import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session | None, None, None]:
    db = None
    try:
        db = SessionLocal()
    except Exception:
        # Degraded mode: allow API routes to continue without DB
        yield None
        return
        
    try:
        yield db
    finally:
        db.close()