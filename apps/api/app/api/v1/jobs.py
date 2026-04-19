from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _serialize_job(j) -> dict:
    """
    Safely serialize a job object regardless of whether it is a
    RepositoryRefreshJob or RepoJob model — they have different field names.
    This unified serializer handles both schemas gracefully.
    """
    # RepositoryRefreshJob uses: event_type, summary, error_message
    # RepoJob uses: job_type, message, error_details, started_at, completed_at
    job_type = getattr(j, "job_type", None) or getattr(j, "event_type", None) or "unknown"
    message = getattr(j, "message", None) or getattr(j, "summary", None) or ""
    error = getattr(j, "error_message", None) or getattr(j, "error_details", None) or None
    started_at = getattr(j, "started_at", None)
    completed_at = getattr(j, "completed_at", None)
    updated_at = getattr(j, "updated_at", None)

    return {
        "id": j.id,
        "repository_id": getattr(j, "repository_id", None),
        "job_type": job_type,
        "event_type": getattr(j, "event_type", None) or job_type,
        "trigger_source": getattr(j, "trigger_source", "system"),
        "branch": getattr(j, "branch", None),
        "changed_files": __import__("json").loads(getattr(j, "changed_files_json", None) or "[]"),
        "status": getattr(j, "status", "unknown"),
        "message": message,
        "summary": message,
        "error_message": error,
        "started_at": started_at.isoformat() if started_at else None,
        "completed_at": (completed_at or updated_at),
        "created_at": j.created_at.isoformat() if j.created_at else None,
        # Legacy compat aliases
        "type": job_type,
        "repo_id": getattr(j, "repository_id", None),
    }


@router.get("")
def list_jobs(
    repo_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    try:
        job_service = JobService(db)
        items, total = job_service.list_jobs(repository_id=repo_id)

        return {
            "items": [_serialize_job(j) for j in items[:limit]],
            "total": total,
            "message": "Jobs retrieved from database.",
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"list_jobs failed: {e}", exc_info=True)
        # Return empty list instead of 500 — never crash the refresh jobs page
        return {
            "items": [],
            "total": 0,
            "message": f"Job history temporarily unavailable: {type(e).__name__}",
        }


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job_service = JobService(db)

    # Try both models
    from app.db.models.repo_job import RepoJob
    from app.db.models.repository_refresh_job import RepositoryRefreshJob

    job = db.get(RepoJob, job_id) or db.get(RepositoryRefreshJob, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return _serialize_job(job)
