from datetime import datetime
from pydantic import BaseModel, Field


class RepoCreateRequest(BaseModel):
    repo_url: str = Field(..., min_length=1)
    branch: str = Field(default="main", min_length=1)
    local_path: str | None = None


class RepoResponse(BaseModel):
    id: str
    repo_url: str
    name: str
    owner: str
    default_branch: str
    local_path: str | None = None
    status: str
    primary_language: str | None = None
    framework: str | None = None
    languages_used: list[str] = []
    created_at: datetime


class RepoListResponse(BaseModel):
    items: list[RepoResponse]
    total: int
