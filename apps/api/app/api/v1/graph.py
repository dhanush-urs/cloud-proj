from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.job_service import JobService
from app.services.repository_service import RepositoryService
from app.graph.graph_service import GraphService
from app.workers.tasks_graph import sync_repository_graph

router = APIRouter(tags=["graph"])


@router.post("/repos/{repo_id}/graph/sync", status_code=status.HTTP_202_ACCEPTED)
def trigger_graph_sync(
    repo_id: str,
    db: Session = Depends(get_db),
):
    repository_service = RepositoryService(db)
    repository = repository_service.get_repository(repo_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    if repository.status not in {"parsed", "indexed"}:
        # In placeholder mode, we might allow indexed repos too
        pass

    job_service = JobService(db)
    job = job_service.create_job(
        repository_id=repo_id,
        job_type="sync_repository_graph",
        status="queued",
        message="Graph sync queued",
    )

    task = sync_repository_graph.delay(repo_id, job.id)
    job_service.update_task_id(job.id, task.id)

    return {
        "message": "Graph sync started",
        "repository_id": repo_id,
        "job_id": job.id,
        "task_id": task.id,
    }


@router.get("/repos/{repo_id}/graph/summary")
def get_graph_summary(
    repo_id: str,
    db: Session = Depends(get_db),
):
    repository_service = RepositoryService(db)
    repository = repository_service.get_repository(repo_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    graph_service = GraphService(db)
    summary = graph_service.get_repository_graph_summary(repo_id)

    return summary
