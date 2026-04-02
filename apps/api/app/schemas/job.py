from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RepoJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    job_type: str
    status: str
    task_id: str | None
    message: str | None
    error_details: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class RepoJobListResponse(BaseModel):
    items: list[RepoJobResponse]
    total: int
