from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.pr_impact import PRImpactRequest, PRImpactResponse
from app.services.pr_impact_service import PRImpactService
from app.services.repository_service import RepositoryService

router = APIRouter(tags=["pr-impact"])


@router.post("/repos/{repo_id}/impact", response_model=PRImpactResponse)
def analyze_repository_pr_impact(
    repo_id: str,
    payload: PRImpactRequest,
    db: Session = Depends(get_db),
):
    repository_service = RepositoryService(db)
    repository = repository_service.get_repository(repo_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    impact_service = PRImpactService(db)
    result = impact_service.analyze_impact(
        repository_id=repo_id,
        changed_files=payload.changed_files,
        max_depth=payload.max_depth,
    )

    return PRImpactResponse(**result)
