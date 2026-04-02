from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.repo_snapshot import RepoSnapshot

router = APIRouter(prefix="/repo-snapshots", tags=["repo-snapshots"])


@router.get("")
def list_repo_snapshots(
    repository_id: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(RepoSnapshot)

    if repository_id:
        stmt = stmt.where(RepoSnapshot.repository_id == repository_id)

    stmt = stmt.order_by(desc(RepoSnapshot.created_at))
    items = list(db.scalars(stmt).all())

    return {
        "items": [
            {
                "id": item.id,
                "repository_id": item.repository_id,
                "branch_name": item.branch_name,
                "commit_sha": item.commit_sha,
                "local_path": item.local_path,
                "created_at": item.created_at,
            }
            for item in items
        ],
        "total": len(items),
    }
