from datetime import datetime

from pydantic import BaseModel


class RefreshJobItem(BaseModel):
    id: str
    repository_id: str
    trigger_source: str
    event_type: str
    branch: str | None = None
    status: str
    changed_files: list[str]
    summary: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class RefreshJobListResponse(BaseModel):
    repository_id: str
    total: int
    items: list[RefreshJobItem]
