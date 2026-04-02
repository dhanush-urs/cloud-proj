from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SymbolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    file_id: str
    name: str
    symbol_type: str
    signature: str | None
    start_line: int
    end_line: int
    created_at: datetime


class SymbolListResponse(BaseModel):
    items: list[SymbolResponse]
    total: int
