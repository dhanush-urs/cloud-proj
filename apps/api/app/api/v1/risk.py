from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.risk import HotspotItem, HotspotListResponse
from app.services.repository_service import RepositoryService
from app.services.risk_service import RiskService

router = APIRouter(tags=["risk"])


@router.get("/repos/{repo_id}/hotspots", response_model=HotspotListResponse)
def get_repository_hotspots(
    repo_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    repository_service = RepositoryService(db)
    repository = repository_service.get_repository(repo_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    risk_service = RiskService(db)
    items = risk_service.get_hotspots(repository_id=repo_id, limit=limit)

    return HotspotListResponse(
        repository_id=repo_id,
        total=len(items),
        items=[HotspotItem(**item) for item in items],
    )
