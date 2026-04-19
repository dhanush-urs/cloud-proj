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
        job.message = "Repository ingestion started"
        repository.status = "indexing"
        job.started_at = utc_now()
        db.commit()

        ingestion_service = IngestionService(db)

        # STAGE: DISCOVER_FILES & CLONE
        job.message = "Stage: DISCOVER_FILES - Cloning repository snapshot"
        db.commit()
        local_path, commit_sha, snapshot = ingestion_service.clone_and_snapshot(repository)
        
        # STAGE: CLASSIFY_FILES & DETECT
        job.message = "Stage: CLASSIFY_FILES - Detecting frameworks and languages"
        db.commit()
        try:
            metadata = ingestion_service.detect_repo_metadata(repository, local_path)
            primary_language = metadata["primary_language"]
            detected_frameworks = metadata["detected_frameworks"]
            repository.primary_language = str(primary_language) if primary_language else "unknown"
            repository.detected_frameworks = str(detected_frameworks) if detected_frameworks else "none"
            db.commit()
        except Exception as e:
            primary_language = getattr(repository, "primary_language", "unknown")
            detected_frameworks = getattr(repository, "detected_frameworks", "none")
            
        # STAGE: EXTRACT_CONTENT
        job.message = "Stage: EXTRACT_CONTENT - Reading text files into inventory"
        db.commit()
        total_files = ingestion_service.ingest_file_inventory(repository, local_path)
        
        repository.status = "indexed"
        db.commit()

        # Track overall success
        pipeline_success = True

        # STAGE: PARSE_REPOSITORY
        job.message = "Stage: PARSE_REPOSITORY - Extracting semantics and computing repo intelligence"
        repository.status = "parsing"
        db.commit()
        try:
            from app.services.semantic_service import SemanticService
            from app.services.repo_intelligence_service import RepoIntelligenceService
            
            semantic_service = SemanticService(db)
            parse_result = semantic_service.parse_repository(repository)
            
            # This calls the LLM for individual file summaries (enrich repository was a placeholder name)
            semantic_service.enrich_repository(repository)
            
            # Hook up the missing full-repo aggregation
            intel_service = RepoIntelligenceService(db)
            intel_service.build_repo_intelligence(repository)
            
            repository.status = "parsed"
        except Exception as _parse_err:
            import traceback as _tb
            print(f"[WARN] Auto-parse and aggregation failed (non-fatal): {_parse_err}")
            job.error_details = (job.error_details or "") + "\nPARSE ERR:\n" + _tb.format_exc()
            repository.status = "parsed_with_errors"
            pipeline_success = False
        db.commit()

        # STAGE: CHUNK_CONTENT & EMBED_CONTENT
        job.message = "Stage: EMBED_CONTENT - Generating vector embeddings for files"
        repository.status = "embedding"
        db.commit()
        try:
            from app.services.embedding_service import EmbeddingService
            embed_service = EmbeddingService(db)
            embed_result = embed_service.embed_repository(repository)
            repository.status = "embedded"
        except Exception as _embed_err:
            import traceback as _tb2
            print(f"[WARN] Auto-embed step failed (non-fatal): {_embed_err}")
            job.error_details = (job.error_details or "") + "\nEMBED ERR:\n" + _tb2.format_exc()
            repository.status = "embedded_with_errors"
            embed_result = {"processed_files": 0, "total_chunks": 0, "embedding_model": "n/a"}
            pipeline_success = False
        db.commit()

        # STAGE: FINALIZE_STATUS
        # Threshold: if we have files, the repository is fundamentally usable.
        if total_files > 0:
            repository.status = "ready"
            job.status = "completed"
            job.message = (
                f"Full pipeline completed: commit={commit_sha[:8]}, "
                f"files={total_files}, "
                f"chunks={embed_result.get('total_chunks', 0)}, "
                f"status={repository.status}"
            )
            if not pipeline_success:
                job.message += " (with secondary stage warnings)"
        else:
            job.status = "failed"
            job.message = "Pipeline failed: No files discovered or indexed."
            repository.status = "failed"
        
        job.completed_at = utc_now()
        db.commit()

        return {
            "status": "completed" if pipeline_success else "failed",
            "repository_id": repository_id,
            "job_id": job_id,
            "snapshot_id": snapshot.id,
            "commit_sha": commit_sha,
            "total_files": total_files,
            "primary_language": primary_language,
            "detected_frameworks": detected_frameworks,
            "total_chunks": embed_result.get("total_chunks", 0),
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
            job.message = f"Repository ingestion failed: {error_msg}"
            job.error_details = traceback.format_exc()
            job.completed_at = utc_now()

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
