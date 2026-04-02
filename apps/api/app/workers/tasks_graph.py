from app.db.models.repo_job import RepoJob
from app.db.models.repository import Repository
from app.db.session import SessionLocal
from app.graph.graph_service import GraphService
from app.utils.time import utc_now
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks_graph.sync_repository_graph")
def sync_repository_graph(repository_id: str, job_id: str) -> dict:
    db = SessionLocal()

    try:
        repository = db.get(Repository, repository_id)
        job = db.get(RepoJob, job_id)

        if not repository or not job:
            return {"status": "error", "message": "Repository or job not found"}

        job.status = "running"
        job.started_at = utc_now()
        job.message = "Graph sync started"
        db.commit()

        graph_service = GraphService(db)
        result = graph_service.sync_repository_graph(repository)

        job.status = "completed"
        job.completed_at = utc_now()
        job.message = (
            f"Graph sync completed: files={result['files_synced']}, "
            f"symbols={result['symbols_synced']}, "
            f"internal_imports={result['internal_import_edges']}"
        )
        db.commit()

        return {
            "status": "completed",
            "repository_id": repository_id,
            "job_id": job_id,
            **result,
        }

    except Exception as exc:
        job = db.get(RepoJob, job_id)

        if job:
            job.status = "failed"
            job.error_details = str(exc)
            job.completed_at = utc_now()
            job.message = "Graph sync failed"
            db.commit()

        return {
            "status": "failed",
            "repository_id": repository_id,
            "job_id": job_id,
            "error": str(exc),
        }

    finally:
        db.close()
