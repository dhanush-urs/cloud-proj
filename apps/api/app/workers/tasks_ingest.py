from app.db.models.repo_job import RepoJob
from app.db.models.repository import Repository
from app.db.session import SessionLocal
from app.services.ingestion_service import IngestionService
from app.utils.time import utc_now
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks_ingest.index_repository")
def index_repository(repository_id: str, job_id: str) -> dict:
    db = SessionLocal()

    try:
        repository = db.get(Repository, repository_id)
        job = db.get(RepoJob, job_id)

        if not repository or not job:
            return {"status": "error", "message": "Repository or job not found"}

        job.status = "running"
        job.started_at = utc_now()
        job.message = "Repository ingestion started"
        repository.status = "indexing"
        db.commit()

        ingestion_service = IngestionService(db)

        local_path, commit_sha, snapshot = ingestion_service.clone_and_snapshot(repository)
        
        try:
            metadata = ingestion_service.detect_repo_metadata(repository, local_path)
            primary_language = metadata["primary_language"]
            detected_frameworks = metadata["detected_frameworks"]
            
            # Persist metadata to the repository model
            repository.primary_language = primary_language
            repository.detected_frameworks = detected_frameworks
            db.commit()
            
        except Exception as e:
            # Fail-soft: save files/chunks even if language detection crashes
            primary_language = getattr(repository, "primary_language", "unknown")
            detected_frameworks = getattr(repository, "detected_frameworks", "none")
            
        total_files = ingestion_service.ingest_file_inventory(repository, local_path)

        repository.status = "indexed"
        job.status = "completed"
        job.completed_at = utc_now()
        job.message = (
            f"Indexed repo snapshot={snapshot.id}, commit={commit_sha[:8]}, "
            f"files={total_files}, primary_language={primary_language}"
        )
        db.commit()

        return {
            "status": "completed",
            "repository_id": repository_id,
            "job_id": job_id,
            "snapshot_id": snapshot.id,
            "commit_sha": commit_sha,
            "total_files": total_files,
            "primary_language": primary_language,
            "detected_frameworks": detected_frameworks,
        }

    except Exception as exc:
        import traceback
        from app.core.config import get_settings
        settings = get_settings()
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        print(f"[ERROR] index_repository failed: {error_msg}")
        traceback.print_exc()

        job = db.get(RepoJob, job_id)
        repository = db.get(Repository, repository_id)

        if job:
            job.status = "failed"
            job.error_details = traceback.format_exc()
            job.completed_at = utc_now()
            job.message = f"Repository ingestion failed: {error_msg}"

        if repository:
            repository.status = "failed"

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
