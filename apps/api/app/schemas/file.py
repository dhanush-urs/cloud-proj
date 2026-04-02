from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    path: str
    language: str | None
    extension: str | None
    file_kind: str
    size_bytes: int
    line_count: int
    is_generated: bool
    is_test: bool
    is_config: bool
    is_doc: bool
    is_vendor: bool
    parse_status: str
    checksum: str | None
    created_at: datetime
    updated_at: datetime


class FileListResponse(BaseModel):
    items: list[FileResponse]
    total: int
