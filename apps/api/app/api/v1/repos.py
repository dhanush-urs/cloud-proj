from __future__ import annotations

import logging
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.file import File
from app.schemas.repository import RepoCreateRequest, RepoListResponse, RepoResponse
from app.services.job_service import JobService
from app.services.repository_service import RepositoryService
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _dispatch_repo_indexing(repo_id: str, job_id: str):
    """Background task to dispatch Celery worker without blocking the HTTP response."""
    db = SessionLocal()
    try:
        from app.workers.tasks_ingest import index_repository
        from app.workers.celery_app import dispatch_task
        task = dispatch_task(index_repository, repo_id, job_id)
        
        job_service = JobService(db)
        job_service.update_task_id(job_id, task.id)
    except Exception as e:
        logger.warning(f"Could not enqueue indexing task: {e}")
    finally:
        db.close()


def _get_languages_used(db: Session, repo_id: str) -> list[str]:
    """Return languages used in the repository, sorted by file count descending.
    Only counts files with a non-null, non-empty language field.
    Result is deterministic and entirely data-driven from indexed files.
    """
    rows = db.execute(
        select(File.language).where(
            File.repository_id == repo_id,
            File.language.isnot(None),
            File.language != "",
        )
    ).scalars().all()
    counts = Counter(lang.strip() for lang in rows if lang and lang.strip())
    # Return sorted by count desc, alphabetical for ties
    return [lang for lang, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]


router = APIRouter(prefix="/repos", tags=["repos"])


@router.post("", response_model=RepoResponse, status_code=status.HTTP_201_CREATED)
def create_repo(payload: RepoCreateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    repository_service = RepositoryService(db)
    job_service = JobService(db)

    try:
        repo = repository_service.create_repository(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to persist repository")
        raise HTTPException(status_code=500, detail={"message": "Failed to create repository", "error": str(e)})

    # Trigger initial indexing task
    try:
        job = job_service.create_job(
            repository_id=repo.id,
            job_type="index_repository",
            status="queued",
            message="Repository indexing queued",
        )
        background_tasks.add_task(_dispatch_repo_indexing, repo.id, job.id)
    except Exception as e:
        logger.warning(f"Could not enqueue indexing task: {e}")

    return repo


@router.get("", response_model=RepoListResponse)
def get_repos(db: Session = Depends(get_db)):
    repository_service = RepositoryService(db)
    repos = repository_service.list_repositories()
    
    items = []
    for repo in repos:
        full_name = getattr(repo, "full_name", "") or ""
        owner = full_name.split("/")[0] if "/" in full_name else "unknown"
        items.append(RepoResponse(
            id=repo.id,
            repo_url=repo.repo_url,
            name=repo.name,
            owner=owner,
            default_branch=repo.default_branch or "main",
            local_path=getattr(repo, "local_path", None),
            status=repo.status,
            primary_language=getattr(repo, "primary_language", "unknown"),
            framework=getattr(repo, "detected_frameworks", "none"),
            languages_used=_get_languages_used(db, repo.id),
            created_at=repo.created_at,
        ))
        
    return RepoListResponse(items=items, total=len(items))


@router.get("/{repo_id}", response_model=RepoResponse)
def get_repo(repo_id: str, db: Session = Depends(get_db)):
    repository_service = RepositoryService(db)
    repo = repository_service.get_repository(repo_id)

    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

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
        primary_language=getattr(repo, "primary_language", "unknown"),
        framework=getattr(repo, "detected_frameworks", "none"),
        languages_used=_get_languages_used(db, repo_id),
        created_at=repo.created_at,
    )


@router.post("/{repo_id}/parse", status_code=status.HTTP_202_ACCEPTED)
def parse_repo(repo_id: str, db: Session = Depends(get_db)):
    repository_service = RepositoryService(db)
    # FIX: job_service was used but never instantiated — was `name 'job_service' is not defined`
    job_service = JobService(db)

    repo = repository_service.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        from app.workers.tasks_parse import parse_repository_semantics
        from app.workers.celery_app import dispatch_task

        # Create job FIRST before setting status, so job record exists even if dispatch fails
        job = job_service.create_job(
            repository_id=repo_id,
            job_type="parse_repository_semantics",
            status="queued",
            message="Semantic parsing queued",
        )

        repo.status = "parsing"
        db.commit()

        task = dispatch_task(parse_repository_semantics, repo_id, job.id)
        job_service.update_task_id(job.id, task.id)

        return {
            "job_id": job.id,
            "task_id": str(task.id),
            "repo_id": repo_id,
            "status": "queued",
            "message": "Repository parse job triggered.",
        }
    except Exception as e:
        logger.error(f"Could not enqueue parse task: {e}", exc_info=True)
        # Try to recover status if job creation failed
        try:
            repo.status = "failed"
            db.commit()
        except Exception:
            pass
        raise HTTPException(status_code=503, detail=f"Task broker unavailable: {e}")
