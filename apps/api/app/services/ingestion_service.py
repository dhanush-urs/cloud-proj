from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.branch import Branch
from app.db.models.file import File
from app.db.models.repo_snapshot import RepoSnapshot
from app.db.models.repository import Repository
from app.parsers.file_classifier import classify_file
from app.parsers.framework_detector import detect_frameworks
from app.parsers.language_detector import detect_file_language, detect_languages
from app.utils.file_utils import count_lines, is_probably_text_file, iter_repo_files, safe_read_text
from app.utils.git_utils import clone_repository
from app.utils.hashing import sha256_file


class IngestionService:
    def __init__(self, db: Session):
        self.db = db

    def clone_and_snapshot(
        self,
        repository: Repository,
        branch: str | None = None,
    ) -> tuple[Path, str, RepoSnapshot]:
        local_path, commit_sha = clone_repository(
            repo_url=repository.repo_url,
            repository_id=repository.id,
            branch=branch or repository.default_branch,
        )

        snapshot = RepoSnapshot(
            repository_id=repository.id,
            branch_name=branch or repository.default_branch or "HEAD",
            commit_sha=commit_sha,
            local_path=str(local_path),
        )

        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)

        existing_branch = self.db.scalar(
            select(Branch).where(
                Branch.repository_id == repository.id,
                Branch.name == snapshot.branch_name,
            )
        )

        if not existing_branch:
            repo_branch = Branch(
                repository_id=repository.id,
                name=snapshot.branch_name,
                latest_commit_sha=commit_sha,
            )
            self.db.add(repo_branch)
        else:
            existing_branch.latest_commit_sha = commit_sha

        repository.default_branch = snapshot.branch_name

        self.db.commit()

        return local_path, commit_sha, snapshot

    def detect_repo_metadata(self, repository: Repository, repo_root: Path) -> dict:
        language_data = detect_languages(repo_root)
        frameworks = detect_frameworks(repo_root)

        repository.primary_language = language_data["primary_language"]
        repository.detected_languages = ",".join(language_data["language_counts"].keys())
        repository.detected_frameworks = ",".join(frameworks)

        self.db.commit()

        return {
            "primary_language": repository.primary_language,
            "detected_languages": language_data["language_counts"],
            "detected_frameworks": frameworks,
            "total_detected_code_files": language_data["total_detected_code_files"],
        }

    def ingest_file_inventory(self, repository: Repository, repo_root: Path) -> int:
        # Clear old inventory for full reindex
        self.db.query(File).filter(File.repository_id == repository.id).delete()
        self.db.commit()

        total_files = 0

        for path in iter_repo_files(repo_root):
            if not path.is_file():
                continue

            relative_path = path.relative_to(repo_root)
            relative_path_str = str(relative_path)
            suffix = path.suffix.lower() or None

            file_meta = classify_file(relative_path)
            language = detect_file_language(relative_path)

            text = safe_read_text(path) if is_probably_text_file(path) else ""
            line_count = count_lines(text) if text else 0

            should_parse = (
                file_meta["file_kind"] in {"source", "test", "config", "build", "script"}
                and not file_meta["is_vendor"]
                and not file_meta["is_generated"]
            )

            file_record = File(
                repository_id=repository.id,
                path=relative_path_str,
                content=text,
                language=language,
                extension=suffix,
                file_kind=file_meta["file_kind"],
                size_bytes=path.stat().st_size,
                line_count=line_count,
                is_generated=file_meta["is_generated"],
                is_test=file_meta["is_test"],
                is_config=file_meta["is_config"],
                is_doc=file_meta["is_doc"],
                is_vendor=file_meta["is_vendor"],
                parse_status="pending" if should_parse else "skipped",
                checksum=sha256_file(path),
            )

            self.db.add(file_record)
            total_files += 1

        repository.total_files = total_files
        self.db.commit()

        return total_files
