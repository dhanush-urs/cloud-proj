from sqlalchemy import select
from app.db.models.repo_job import RepoJob
from app.db.models.repository import Repository
from app.db.models.repo_snapshot import RepoSnapshot
from app.db.session import SessionLocal
from app.services.semantic_service import SemanticService
from app.utils.time import utc_now
import logging
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(name="app.workers.tasks_parse.parse_repository_semantics")
def parse_repository_semantics(repository_id: str, job_id: str) -> dict:
    from app.services.ingestion_service import IngestionService
    db = SessionLocal()

    try:
        repository = db.get(Repository, repository_id)
        job = db.get(RepoJob, job_id)

        if not repository or not job:
            return {"status": "error", "message": "Repository or job not found"}

        job.status = "running"
        job.started_at = utc_now()
        job.message = "Repository ingestion & parsing started"
        repository.status = "parsing"
        db.commit()

        # Step 1: Ingest (Clone, Detect, Persist Text Files)
        ingestion_service = IngestionService(db)
        
        # Check if we already have a snapshot (from index_repository task or previous run)
        semantic_service = SemanticService(db)
        snapshot_path = semantic_service._get_repo_root(repository)
        
        if snapshot_path and snapshot_path.exists():
            local_path = snapshot_path
            # We need the snapshot object for the return dict
            snapshot = db.scalar(
                select(RepoSnapshot)
                .where(RepoSnapshot.repository_id == repository.id)
                .order_by(RepoSnapshot.created_at.desc())
                .limit(1)
            )
            commit_sha = snapshot.commit_sha
        else:
            local_path, commit_sha, snapshot = ingestion_service.clone_and_snapshot(repository)
        
        try:
            metadata = ingestion_service.detect_repo_metadata(repository, local_path)
            primary_language = metadata["primary_language"]
        except Exception:
            primary_language = getattr(repository, "primary_language", "unknown")
            
        total_files = ingestion_service.ingest_file_inventory(repository, local_path)

        # Step 2: Semantic Parse 
        result = semantic_service.parse_repository(repository)
        
        # Step 3: LLM Enrichment
        enrich_result = semantic_service.enrich_repository(repository)
        logger.info(f"Enrichment result: {enrich_result.get('status')}")

        repository.status = "parsed"

        job.status = "completed"
        job.completed_at = utc_now()
        job.message = (
            f"Parsing completed: parsed={result['parsed_files']}, "
            f"symbols={result['total_symbols']}, deps={result['total_dependencies']}, "
            f"graph_resolved={result.get('resolved_dependencies', 0)}"
        )
        db.commit()

        return {
            "status": "completed",
            "repository_id": repository_id,
            "job_id": job_id,
            "snapshot_id": snapshot.id,
            "total_files": total_files,
            "primary_language": primary_language,
            **result,
        }

    except Exception as exc:
        import traceback
        from app.core.config import get_settings
        settings = get_settings()
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        print(f"[ERROR] parse_repository_semantics failed: {error_msg}")
        traceback.print_exc()

        job = db.get(RepoJob, job_id)
        repository = db.get(Repository, repository_id)

        if job:
            job.status = "failed"
            job.error_details = traceback.format_exc()
            job.completed_at = utc_now()
            job.message = f"Semantic parsing failed: {error_msg}"

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
