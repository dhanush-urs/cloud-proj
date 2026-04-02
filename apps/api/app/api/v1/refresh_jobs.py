import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.repository_refresh_job import RepositoryRefreshJob
from app.schemas.refresh_jobs import RefreshJobItem, RefreshJobListResponse
from app.services.repository_service import RepositoryService

router = APIRouter(tags=["refresh-jobs"])


@router.get("/repos/{repo_id}/refresh-jobs", response_model=RefreshJobListResponse)
def list_repository_refresh_jobs(
    repo_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    repository_service = RepositoryService(db)
    repository = repository_service.get_repository(repo_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    jobs = list(
        db.scalars(
            select(RepositoryRefreshJob)
            .where(RepositoryRefreshJob.repository_id == repo_id)
            .order_by(RepositoryRefreshJob.created_at.desc())
            .limit(limit)
        ).all()
    )

    return RefreshJobListResponse(
        repository_id=repo_id,
        total=len(jobs),
        items=[
            RefreshJobItem(
                id=job.id,
                repository_id=job.repository_id,
                trigger_source=job.trigger_source,
                event_type=job.event_type,
                branch=job.branch,
                status=job.status,
                changed_files=json.loads(job.changed_files_json),
                summary=job.summary,
                error_message=job.error_message,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
            for job in jobs
        ],
    )


@router.get("/refresh-jobs/{job_id}", response_model=RefreshJobItem)
def get_refresh_job(
    job_id: str,
    db: Session = Depends(get_db),
):
    job = db.scalar(
        select(RepositoryRefreshJob).where(RepositoryRefreshJob.id == job_id)
    )

    if not job:
        raise HTTPException(status_code=404, detail="Refresh job not found")

    return RefreshJobItem(
        id=job.id,
        repository_id=job.repository_id,
        trigger_source=job.trigger_source,
        event_type=job.event_type,
        branch=job.branch,
        status=job.status,
        changed_files=json.loads(job.changed_files_json),
        summary=job.summary,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
