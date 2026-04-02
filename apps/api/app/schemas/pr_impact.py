from pydantic import BaseModel, Field


class PRImpactRequest(BaseModel):
    changed_files: list[str] = Field(..., min_length=1)
    max_depth: int = Field(default=3, ge=1, le=8)


class ImpactedFileItem(BaseModel):
    file_id: str
    path: str
    language: str | None
    depth: int
    inbound_dependencies: int
    outbound_dependencies: int
    risk_score: float
    impact_score: float


class ReviewerSuggestion(BaseModel):
    reviewer_hint: str
    reason: str


class PRImpactResponse(BaseModel):
    repository_id: str
    changed_files: list[str]
    impacted_count: int
    risk_level: str
    total_impact_score: float
    summary: str
    impacted_files: list[ImpactedFileItem]
    reviewer_suggestions: list[ReviewerSuggestion]
