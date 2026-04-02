from datetime import datetime

from pydantic import BaseModel, Field


class GenerateOnboardingRequest(BaseModel):
    top_files: int = Field(default=10, ge=3, le=30)
    include_hotspots: bool = True
    include_search_context: bool = True


class GenerateOnboardingResponse(BaseModel):
    message: str
    repository_id: str
    document_id: str
    generation_mode: str
    llm_model: str | None = None


class OnboardingDocumentResponse(BaseModel):
    id: str
    repository_id: str
    version: int
    title: str
    content_markdown: str
    generation_mode: str
    llm_model: str | None
    created_at: datetime
