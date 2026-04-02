import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.onboarding import (
    GenerateOnboardingRequest,
    GenerateOnboardingResponse,
    OnboardingDocumentResponse,
)
from app.services.onboarding_service import OnboardingService
from app.services.repository_service import RepositoryService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["onboarding"])


@router.post("/repos/{repo_id}/onboarding/generate", response_model=GenerateOnboardingResponse)
def generate_repository_onboarding(
    repo_id: str,
    payload: GenerateOnboardingRequest,
    db: Session = Depends(get_db),
):
    repository_service = RepositoryService(db)
    repository = repository_service.get_repository(repo_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Only accept ORM Repository objects — schema-only (in-memory) repos lack fields
    # needed by OnboardingService (e.g. .repo_url, .default_branch as model attrs)
    if not hasattr(repository, "default_branch"):
        raise HTTPException(
            status_code=409,
            detail="Repository has not been fully ingested yet. Onboarding requires a persisted repository.",
        )

    try:
        onboarding_service = OnboardingService(db)
        doc = onboarding_service.generate_document(
            repository=repository,
            top_files=payload.top_files,
            include_hotspots=payload.include_hotspots,
            include_search_context=payload.include_search_context,
        )
    except Exception as exc:
        logger.exception(f"Onboarding generation failed for repo {repo_id}")
        raise HTTPException(status_code=500, detail=f"Onboarding generation failed: {exc}")

    return GenerateOnboardingResponse(
        message="Onboarding document generated successfully",
        repository_id=repo_id,
        document_id=doc.id,
        generation_mode=doc.generation_mode,
        llm_model=doc.llm_model,
    )


@router.get("/repos/{repo_id}/onboarding", response_model=OnboardingDocumentResponse)
def get_latest_repository_onboarding(
    repo_id: str,
    db: Session = Depends(get_db),
):
    repository_service = RepositoryService(db)
    repository = repository_service.get_repository(repo_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    onboarding_service = OnboardingService(db)
    doc = onboarding_service.get_latest_document(repo_id)

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="No onboarding document found. Generate one first.",
        )

    return OnboardingDocumentResponse(
        id=doc.id,
        repository_id=doc.repository_id,
        version=doc.version,
        title=doc.title,
        content_markdown=doc.content_markdown,
        generation_mode=doc.generation_mode,
        llm_model=doc.llm_model,
        created_at=doc.created_at,
    )
