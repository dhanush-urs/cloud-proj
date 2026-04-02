from app.db.models.repo_job import RepoJob
from app.db.models.repository import Repository
from app.db.session import SessionLocal
from app.services.embedding_service import EmbeddingService
from app.utils.time import utc_now
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks_embed.embed_repository")
def embed_repository(repository_id: str, job_id: str) -> dict:
    db = SessionLocal()

    try:
        repository = db.get(Repository, repository_id)
        job = db.get(RepoJob, job_id)

        if not repository or not job:
            return {"status": "error", "message": "Repository or job not found"}

        job.status = "running"
        job.started_at = utc_now()
        job.message = "Embedding pipeline started"
        db.commit()

        embedding_service = EmbeddingService(db)
        result = embedding_service.embed_repository(repository)

        repository.status = "embedded"

        job.status = "completed"
        job.completed_at = utc_now()
        job.message = (
            f"Embedding completed: files={result['processed_files']}, "
            f"chunks={result['total_chunks']}, model={result['embedding_model']}"
        )
        db.commit()

        return {
            "status": "completed",
            "repository_id": repository_id,
            "job_id": job_id,
            **result,
        }

    except Exception as exc:
        import traceback
        from app.core.config import get_settings
        settings = get_settings()
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        print(f"[ERROR] embed_repository failed: {error_msg}")
        traceback.print_exc()

        job = db.get(RepoJob, job_id)
        repo = db.get(Repository, repository_id)

        if job:
            job.status = "failed"
            job.error_details = traceback.format_exc()
            job.completed_at = utc_now()
            job.message = f"Embedding pipeline failed: {error_msg}"

        if repo:
            # Revert to parsed so the user can see the real state and retry
            repo.status = "parsed"

        db.commit()

        return {
            "status": "failed",
            "repository_id": repository_id,
            "job_id": job_id,
            "error": error_msg,
            "traceback": traceback.format_exc() if settings.DEBUG else None,
        }

    finally:
        db.close()
