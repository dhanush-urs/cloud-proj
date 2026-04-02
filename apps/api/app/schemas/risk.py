from pydantic import BaseModel


class HotspotItem(BaseModel):
    file_id: str
    path: str
    language: str | None
    file_kind: str
    risk_score: float
    complexity_score: float
    dependency_score: float
    change_proneness_score: float
    test_proximity_score: float
    symbol_count: int
    inbound_dependencies: int
    outbound_dependencies: int
    risk_level: str


class HotspotListResponse(BaseModel):
    repository_id: str
    total: int
    items: list[HotspotItem]
