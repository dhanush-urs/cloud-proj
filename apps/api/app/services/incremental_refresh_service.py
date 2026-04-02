import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.file import File
from app.db.models.repository import Repository
from app.db.models.repository_refresh_job import RepositoryRefreshJob
from app.services.embedding_service import EmbeddingService
from app.services.git_sync_service import GitSyncService
from app.services.incremental_parser_service import IncrementalParserService
from app.services.repository_service import RepositoryService


class IncrementalRefreshService:
    def __init__(self, db: Session):
        self.db = db
        self.repository_service = RepositoryService(db)
        self.embedding_service = EmbeddingService(db)
        self.git_sync_service = GitSyncService()
        self.incremental_parser_service = IncrementalParserService(db)

    def create_refresh_job(
        self,
        repository: Repository,
        event_type: str,
        branch: str | None,
        changed_files: list[str],
        trigger_source: str = "webhook",
    ) -> RepositoryRefreshJob:
        job = RepositoryRefreshJob(
            repository_id=repository.id,
            trigger_source=trigger_source,
            event_type=event_type,
            branch=branch,
            status="queued",
            changed_files_json=json.dumps(changed_files),
            summary=f"Queued refresh for {len(changed_files)} changed files",
        )
        self.db.add(job)

        repository.status = "refresh_queued"
        self.db.add(repository)

        self.db.commit()
        self.db.refresh(job)
        return job

    def process_refresh_job(self, job_id: str) -> RepositoryRefreshJob:
        job = self.db.scalar(
            select(RepositoryRefreshJob).where(RepositoryRefreshJob.id == job_id)
        )

        if not job:
            raise ValueError("Refresh job not found")

        repository = self.repository_service.get_repository(job.repository_id)
        if not repository:
            job.status = "failed"
            job.error_message = "Repository not found"
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)
            return job

        changed_files = json.loads(job.changed_files_json)

        job.status = "processing"
        repository.status = "refreshing"

        self.db.add(job)
        self.db.add(repository)
        self.db.commit()

        try:
            # 1) Always sync latest git state first
            self.git_sync_service.sync_repository(
                local_path=repository.local_path,
                branch=job.branch or repository.default_branch,
            )

            # 2) Incremental refresh logic
            if not changed_files:
                self._full_refresh_fallback(repository)
                job.summary = "No changed files available; repository marked refresh_pending"
            else:
                refreshed_count = self._refresh_changed_files(repository, changed_files)
                job.summary = f"Incrementally refreshed {refreshed_count} changed files"

            job.status = "completed"
            job.error_message = None

            if repository.status != "refresh_pending":
                repository.status = "parsed"

        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)

            repository.status = "refresh_failed"

        finally:
            from datetime import datetime
            job.updated_at = datetime.utcnow()
            self.db.add(job)
            self.db.add(repository)
            self.db.commit()
            self.db.refresh(job)

        return job

    def _full_refresh_fallback(self, repository: Repository) -> None:
        repository.status = "refresh_pending"
        self.db.add(repository)
        self.db.commit()

    def _refresh_changed_files(self, repository: Repository, changed_paths: list[str]) -> int:
        repo_path = Path(repository.local_path)
        if not repo_path.exists():
            raise ValueError("Local repository path does not exist")

        refreshed = 0

        for rel_path in changed_paths:
            changed = self._refresh_single_file(repository, repo_path, rel_path)
            if changed:
                refreshed += 1

        return refreshed

    def _refresh_single_file(self, repository: Repository, repo_path: Path, rel_path: str) -> bool:
        absolute_path = repo_path / rel_path

        existing_file = self.db.scalar(
            select(File).where(
                File.repository_id == repository.id,
                File.path == rel_path,
            )
        )

        if not absolute_path.exists():
            if existing_file:
                self._delete_file_fully(existing_file)
                return True
            return False

        if not absolute_path.is_file():
            return False

        content = absolute_path.read_text(encoding="utf-8", errors="ignore")
        line_count = len(content.splitlines())

        if existing_file:
            existing_file.content = content
            existing_file.line_count = line_count
            existing_file.parse_status = "parsed"
            existing_file.language = self._detect_language(rel_path)
            existing_file.file_kind = self._detect_file_kind(rel_path)
            file_row = existing_file
        else:
            file_row = File(
                repository_id=repository.id,
                path=rel_path,
                content=content,
                line_count=line_count,
                parse_status="parsed",
                language=self._detect_language(rel_path),
                file_kind=self._detect_file_kind(rel_path),
                is_generated=False,
                is_vendor=False,
            )
            self.db.add(file_row)
            self.db.flush()

        self.db.add(file_row)
        self.db.commit()
        self.db.refresh(file_row)

        # Real incremental parse rebuild
        self.incremental_parser_service.reparse_file(repository, file_row)

        # Re-embed changed file
        self.embedding_service.embed_single_file(repository.id, file_row.id)

        return True

    def _delete_file_fully(self, file_row: File) -> None:
        # Let the incremental parser delete parse artifacts
        self.incremental_parser_service._delete_existing_parse_artifacts(file_row)

        # Delete embeddings
        from sqlalchemy import delete
        from app.db.models.embedding_chunk import EmbeddingChunk

        self.db.execute(
            delete(EmbeddingChunk).where(
                EmbeddingChunk.repository_id == file_row.repository_id,
                EmbeddingChunk.file_id == file_row.id,
            )
        )

        self.db.delete(file_row)
        self.db.commit()

    def _detect_language(self, path: str) -> str | None:
        lower = path.lower()

        if lower.endswith(".py"):
            return "python"
        if lower.endswith(".js"):
            return "javascript"
        if lower.endswith(".ts"):
            return "typescript"
        if lower.endswith(".tsx"):
            return "tsx"
        if lower.endswith(".jsx"):
            return "jsx"
        if lower.endswith(".java"):
            return "java"
        if lower.endswith(".go"):
            return "go"
        if lower.endswith(".rs"):
            return "rust"
        if lower.endswith(".md"):
            return "markdown"

        return None

    def _detect_file_kind(self, path: str) -> str:
        lower = path.lower()

        if any(lower.endswith(ext) for ext in [".yml", ".yaml", ".toml", ".ini", ".json"]):
            return "config"

        if any(lower.endswith(ext) for ext in [".md", ".txt", ".rst"]):
            return "docs"

        if "test" in lower:
            return "test"

        if any(lower.endswith(ext) for ext in [".sh", ".bash"]):
            return "script"

        return "source"
