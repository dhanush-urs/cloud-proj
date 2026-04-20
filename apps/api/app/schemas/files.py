from pydantic import BaseModel


class FileItem(BaseModel):
    id: str
    path: str
    language: str | None = None
    file_kind: str
    line_count: int | None = None
    parse_status: str | None = None


class FileListResponse(BaseModel):
    repository_id: str
    status: str | None = None
    total: int
    items: list[FileItem]


class FileDetailResponse(BaseModel):
    id: str
    repository_id: str
    path: str
    language: str | None = None
    file_kind: str
    line_count: int | None = None
    parse_status: str | None = None
    is_generated: bool = False
    is_vendor: bool = False
    content: str | None = None
    raw_url: str | None = None
    is_binary: bool = False
