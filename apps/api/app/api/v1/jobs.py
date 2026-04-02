from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(
    repo_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    job_service = JobService(db)
    items, total = job_service.list_jobs(repository_id=repo_id)

    return {
        "items": [
            {
                "id": j.id,
                "repo_id": j.repository_id,
                "type": j.job_type,
                "status": j.status,
                "message": j.message,
                "created_at": j.created_at,
            }
            for j in items[:limit]
        ],
        "total": total,
        "message": "Real jobs retrieved from database."
    }


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job_service = JobService(db)
    # Simple direct access for now as JobService doesn't have get_job
    from app.db.models.repo_job import RepoJob
    job = db.get(RepoJob, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "id": job.id,
        "repo_id": job.repository_id,
        "type": job.job_type,
        "status": job.status,
        "message": job.message,
        "error_details": job.error_details,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }
