from __future__ import annotations

from datetime import datetime, timezone
from typing import List
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models.repository import Repository
from app.schemas.repository import RepoCreateRequest, RepoResponse


# In-memory fallback store for Module 1 / degraded mode
_IN_MEMORY_REPOS: List[RepoResponse] = []


def _parse_github_repo_url(repo_url: str) -> tuple[str, str]:
    """
    Accepts:
    - https://github.com/owner/name
    - https://github.com/owner/name.git
    """
    parsed = urlparse(repo_url)
    path_parts = [part for part in parsed.path.strip("/").split("/") if part]

    if len(path_parts) < 2:
        raise ValueError("Invalid GitHub repository URL")

    owner = path_parts[0]
    name = path_parts[1].removesuffix(".git")

    return owner, name


class RepositoryService:
    def __init__(self, db: Session | None = None):
        self.db = db

    def create_repository(self, payload: RepoCreateRequest) -> RepoResponse:
        owner, name = _parse_github_repo_url(payload.repo_url)

        # Check if already exists
        existing = self.get_repository_by_url(payload.repo_url)
        if existing:
            return RepoResponse(
                id=existing.id,
                repo_url=existing.repo_url,
                name=existing.name,
                owner=owner,
                default_branch=existing.default_branch or payload.branch,
                local_path=existing.local_path,
                status=existing.status,
                last_error=existing.last_error,
                primary_language=existing.primary_language,
                framework=existing.detected_frameworks,
                created_at=existing.created_at,
            )

        repo_data = {
            "id": str(uuid4()),
            "repo_url": payload.repo_url,
            "name": name,
            "full_name": f"{owner}/{name}",
            "owner": owner,
            "branch": payload.branch,
            "status": "connected",
            "created_at": datetime.now(timezone.utc),
        }

        # Try DB first
        if self.db:
            try:
                db_repo = Repository(
                    id=repo_data["id"],
                    name=repo_data["name"],
                    full_name=repo_data["full_name"],
                    repo_url=repo_data["repo_url"],
                    default_branch=repo_data["branch"],
                    local_path=payload.local_path,
                    status=repo_data["status"],
                )
                self.db.add(db_repo)
                self.db.commit()
                self.db.refresh(db_repo)
                
                return RepoResponse(
                    id=db_repo.id,
                    repo_url=db_repo.repo_url,
                    name=db_repo.name,
                    owner=owner,
                    default_branch=db_repo.default_branch,
                    local_path=db_repo.local_path,
                    status=db_repo.status,
                    last_error=db_repo.last_error,
                    primary_language=db_repo.primary_language,
                    framework=db_repo.detected_frameworks,
                    created_at=db_repo.created_at,
                )
            except Exception as e:
                self.db.rollback()
                raise ValueError(f"Failed to create repository in database: {str(e)}")

        # Fallback to in-memory only if no DB
        repo = RepoResponse(**repo_data)
        _IN_MEMORY_REPOS.append(repo)
        return repo

    def get_repository(self, repo_id: str) -> "RepoResponse | Repository | None":
        if self.db:
            try:
                repo = self.db.get(Repository, repo_id)
                if repo:
                    return repo
            except Exception:
                # Invalid UUID format or other DB error — treat as not found
                self.db.rollback()

        for r in _IN_MEMORY_REPOS:
            if r.id == repo_id:
                return r
        return None

    def get_repository_by_url(self, repo_url: str | None) -> Repository | None:
        if not repo_url or not self.db:
            return None

        # Try exact match, then case-insensitive if needed
        repo = self.db.scalar(
            select(Repository).where(Repository.repo_url == repo_url)
        )
        return repo

    def list_repositories(self) -> list[RepoResponse]:
        if self.db:
            try:
                stmt = select(Repository).order_by(Repository.created_at.desc())
                db_repos = list(self.db.scalars(stmt).all())
                return [
                    RepoResponse(
                        id=r.id,
                        repo_url=r.repo_url,
                        name=r.name,
                        owner=r.full_name.split("/")[0] if "/" in r.full_name else "unknown",
                        default_branch=r.default_branch,
                        status=r.status,
                        last_error=r.last_error,
                        primary_language=r.primary_language,
                        framework=r.detected_frameworks,
                        created_at=r.created_at,
                    )
                    for r in db_repos
                ]
            except Exception:
                pass

        return _IN_MEMORY_REPOS


# Module-level exports for backward compatibility
def create_repository(payload: RepoCreateRequest, db: Session | None = None) -> RepoResponse:
    return RepositoryService(db).create_repository(payload)


def get_repository(repo_id: str, db: Session | None = None) -> RepoResponse | Repository | None:
    return RepositoryService(db).get_repository(repo_id)


def list_repositories(db: Session | None = None) -> list[RepoResponse]:
    return RepositoryService(db).list_repositories()
