from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.symbol import Symbol
from app.db.models.dependency_edge import DependencyEdge
from app.services.repository_service import RepositoryService
from app.services.job_service import JobService
from app.workers.tasks_parse import parse_repository_semantics

router = APIRouter(prefix="/semantic", tags=["semantic"])


@router.post("/repo/{repo_id}/parse", status_code=status.HTTP_202_ACCEPTED)
def trigger_semantic_parse(
    repo_id: str,
    db: Session = Depends(get_db),
):
    repository_service = RepositoryService(db)
    repo = repository_service.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

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
        "repo_id": repo_id,
        "status": "queued",
    }


@router.get("/repo/{repo_id}/summary")
def get_repo_semantic_summary(
    repo_id: str,
    db: Session = Depends(get_db),
):
    repository_service = RepositoryService(db)
    repo = repository_service.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    symbol_count = db.scalar(select(func.count(Symbol.id)).where(Symbol.repository_id == repo_id)) or 0
    dep_count = db.scalar(select(func.count(DependencyEdge.id)).where(DependencyEdge.repository_id == repo_id)) or 0

    return {
        "repo_id": repo_id,
        "status": getattr(repo, "status", "unknown"),
        "summary": {
            "symbol_count": symbol_count,
            "dependency_edge_count": dep_count,
        }
    }


@router.get("/repo/{repo_id}/symbols")
def list_repo_symbols(
    repo_id: str,
    kind: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    stmt = select(Symbol).where(Symbol.repository_id == repo_id)
    if kind:
        stmt = stmt.where(Symbol.kind == kind)
    
    stmt = stmt.limit(limit)
    symbols = db.scalars(stmt).all()
    
    return {
        "repo_id": repo_id,
        "total": len(symbols),
        "items": [
            {
                "id": s.id,
                "name": s.name,
                "kind": s.kind,
                "file_id": s.file_id,
                "start_line": s.start_line,
            }
            for s in symbols
        ]
    }
