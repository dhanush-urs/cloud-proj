from datetime import datetime

from pydantic import BaseModel, Field


class EmbedRepositoryResponse(BaseModel):
    message: str
    repository_id: str
    job_id: str
    task_id: str


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResultItem(BaseModel):
    chunk_id: str
    file_id: str | None
    file_path: str | None
    score: float
    chunk_type: str
    start_line: int | None
    end_line: int | None
    snippet: str


class SearchResponse(BaseModel):
    query: str
    total: int
    items: list[SearchResultItem]


class AskRepoRequest(BaseModel):
    question: str = Field(..., min_length=3)
    top_k: int = Field(default=5, ge=1, le=10)


class AskRepoCitation(BaseModel):
    file_id: str | None
    file_path: str | None
    start_line: int | None
    end_line: int | None
    chunk_id: str
    match_type: str | None = None


class AskRepoResponse(BaseModel):
    question: str
    answer: str
    citations: list[AskRepoCitation]
    mode: str
    llm_model: str | None = None
    confidence: str | None = None
    notes: list[str] = []
    query_type: str | None = None
    answer_mode: str | None = None
    snippet_found: bool | None = None
    # Line-level resolution fields (populated for line_impact / line_change_impact queries)
    resolved_file: str | None = None
    resolved_line_number: int | None = None
    matched_line: str | None = None
    enclosing_scope: str | None = None
    line_type: str | None = None
    rename_analysis: dict | None = None


class EmbeddingChunkItem(BaseModel):
    id: str
    repository_id: str
    file_id: str | None
    chunk_type: str
    content: str
    start_line: int | None
    end_line: int | None
    embedding_model: str | None
    created_at: datetime


class EmbeddingChunkListResponse(BaseModel):
    items: list[EmbeddingChunkItem]
    total: int
