from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DependencyEdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    source_file_id: str | None
    target_file_id: str | None
    edge_type: str
    source_ref: str | None
    target_ref: str | None
    created_at: datetime


class DependencyEdgeListResponse(BaseModel):
    items: list[DependencyEdgeResponse]
    total: int
