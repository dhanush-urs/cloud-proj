from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.repository import RepoCreateRequest, RepoListResponse, RepoResponse
from app.services.job_service import JobService
from app.services.repository_service import RepositoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repos", tags=["repos"])


@router.post("", response_model=RepoResponse, status_code=status.HTTP_201_CREATED)
def create_repo(payload: RepoCreateRequest, db: Session = Depends(get_db)):
    repository_service = RepositoryService(db)
    job_service = JobService(db)

    try:
        repo = repository_service.create_repository(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to persist repository")
        raise HTTPException(status_code=500, detail={"message": "Failed to create repository", "error": str(e)})

    # Return repo with connected status, and trigger initial indexing.
    try:
        from app.workers.tasks_ingest import index_repository

        job = job_service.create_job(
            repository_id=repo.id,
            job_type="index_repository",
            status="queued",
            message="Repository indexing queued",
        )
        task = index_repository.delay(repo.id, job.id)
        job_service.update_task_id(job.id, task.id)
    except Exception as e:
        logger.warning(f"Could not enqueue indexing task: {e}")

    return repo


@router.get("", response_model=RepoListResponse)
def get_repos(db: Session = Depends(get_db)):
    repository_service = RepositoryService(db)
    items = repository_service.list_repositories()
    return RepoListResponse(items=items, total=len(items))


@router.get("/{repo_id}", response_model=RepoResponse)
def get_repo(repo_id: str, db: Session = Depends(get_db)):
    repository_service = RepositoryService(db)
    repo = repository_service.get_repository(repo_id)

    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # If it's an ORM model, convert it to the response schema
    if hasattr(repo, "default_branch"):
        full_name = getattr(repo, "full_name", "") or ""
        owner = full_name.split("/")[0] if "/" in full_name else "unknown"
        return RepoResponse(
            id=repo.id,
            repo_url=repo.repo_url,
            name=repo.name,
            owner=owner,
            default_branch=repo.default_branch or "main",
            local_path=getattr(repo, "local_path", None),
            status=repo.status,
            last_error=getattr(repo, "last_error", None),
            primary_language=getattr(repo, "primary_language", "unknown"),
            framework=getattr(repo, "detected_frameworks", "none"),
            created_at=repo.created_at,
        )

    return repo


@router.post("/{repo_id}/parse", status_code=status.HTTP_202_ACCEPTED)
def parse_repo(repo_id: str, db: Session = Depends(get_db)):
    repository_service = RepositoryService(db)
    repo = repository_service.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        from app.workers.tasks_parse import parse_repository_semantics  # lazy import

        repo.status = "parsing"
        db.commit()

        job_service = JobService(db)
        job = job_service.create_job(
            repository_id=repo_id,
            job_type="parse_repository_semantics",
            status="queued",
            message="Semantic parsing queued",
        )
        task = parse_repository_semantics.delay(repo_id, job.id)
        job_service.update_task_id(job.id, task.id)
        return {
            "job_id": job.id,
            "task_id": task.id,
            "repo_id": repo_id,
            "status": "queued",
            "message": "Repository parse job triggered.",
        }
    except Exception as e:
        logger.warning(f"Could not enqueue parse task: {e}")
        raise HTTPException(status_code=503, detail=f"Task broker unavailable: {e}")
