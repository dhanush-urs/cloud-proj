from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select as _select
from sqlalchemy.orm import Session
import logging

from app.api.deps import get_db
from app.schemas.search import (
    AskRepoRequest,
    AskRepoResponse,
    EmbedRepositoryResponse,
    EmbeddingChunkListResponse,
    EmbeddingChunkItem,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.services.embedding_service import EmbeddingService
from app.services.job_service import JobService
from app.services.rag_service import RAGService
from app.services.repository_service import RepositoryService
from app.workers.tasks_embed import embed_repository
from app.workers.celery_app import dispatch_task

router = APIRouter(tags=["search"])
logger = logging.getLogger(__name__)


@router.post("/repos/{repo_id}/embed", response_model=EmbedRepositoryResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_repository_embedding(
    repo_id: str,
    db: Session = Depends(get_db),
):
    repository_service = RepositoryService(db)
    repository = repository_service.get_repository(repo_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    EMBEDDABLE_STATUSES = {"indexed", "parsed", "embedded", "ready", "success"}
    if repository.status not in EMBEDDABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Repository must be indexed or parsed before embedding (current: {repository.status})",
        )

    job_service = JobService(db)
    job = job_service.create_job(
        repository_id=repo_id,
        job_type="embed_repository",
        status="queued",
        message="Embedding pipeline queued",
    )

    repository.status = "embedding"
    db.commit()

    task = dispatch_task(embed_repository, repo_id, job.id)
    job_service.update_task_id(job.id, task.id)

    return EmbedRepositoryResponse(
        message="Embedding started",
        repository_id=repo_id,
        job_id=job.id,
        task_id=task.id,
    )


@router.post("/repos/{repo_id}/search", response_model=SearchResponse)
def search_repository(
    repo_id: str,
    payload: SearchRequest,
    db: Session = Depends(get_db),
):
    repository_service = RepositoryService(db)
    repository = repository_service.get_repository(repo_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    embedding_service = EmbeddingService(db)
    results = embedding_service.hybrid_search(
        repository_id=repo_id,
        query=payload.query,
        top_k=payload.top_k,
    )

    items = [SearchResultItem(**item) for item in results]

    return SearchResponse(
        repository_id=repo_id,
        query=payload.query,
        total=len(items),
        items=items,
    )


@router.post("/repos/{repo_id}/ask", response_model=AskRepoResponse)
def ask_repository(
    repo_id: str,
    payload: AskRepoRequest,
    db: Session = Depends(get_db),
):
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty")

    repository_service = RepositoryService(db)
    repository = repository_service.get_repository(repo_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    # CAPABILITY CHECK: determine what the repo can actually serve, regardless
    # of status string.  A re-index that failed at clone time may have left the
    # status as "failed" even though a previous run produced files and chunks.
    from sqlalchemy import func as _func
    from app.db.models.embedding_chunk import EmbeddingChunk as _EC
    from app.db.models.file import File as _File

    _chunk_count = db.scalar(
        _select(_func.count(_EC.id)).where(_EC.repository_id == repo_id)
    ) or 0
    _file_count = db.scalar(
        _select(_func.count(_File.id)).where(_File.repository_id == repo_id)
    ) or 0

    # Hard-refuse only when the repo is actively being indexed OR has truly
    # nothing usable (no files, no chunks).
    ACTIVE_STATUSES = {"indexing", "parsing", "embedding", "connected", "pending", "queued"}
    if repository.status in ACTIVE_STATUSES:
        return AskRepoResponse(
            question=question,
            answer="The repository is currently being indexed, so Ask Repo cannot produce grounded answers yet. Please retry after indexing completes.",
            citations=[],
            mode="refusal",
            confidence="low",
            query_type="refusal",
            answer_mode="general",
            llm_model=None,
            snippet_found=False,
            notes=[f"Repo status: {repository.status}"]
        )

    if _chunk_count == 0 and _file_count == 0:
        # Truly nothing — failed with no content at all.
        return AskRepoResponse(
            question=question,
            answer="The repository has no indexed content yet. Please add/index the repository before using Ask Repo.",
            citations=[],
            mode="refusal",
            confidence="low",
            query_type="refusal",
            answer_mode="general",
            llm_model=None,
            snippet_found=False,
            notes=[f"Repo status: {repository.status}, files: 0, chunks: 0"]
        )

    # Inventory-only: files exist but no chunks — give a clear degraded response.
    if _chunk_count == 0 and _file_count > 0:
        return AskRepoResponse(
            question=question,
            answer=(
                f"This repository is file-indexed ({_file_count} files), but semantic embeddings are not generated yet. "
                "Ask Repo requires embeddings for grounded retrieval and synthesis. Trigger embedding to enable full-quality answers."
            ),
            citations=[],
            mode="degraded",
            confidence="low",
            query_type="degraded",
            answer_mode="general",
            llm_model=None,
            snippet_found=False,
            notes=["Repository is indexed but has no semantic embeddings."]
        )

    rag_service = RAGService(db)
    try:
        result = rag_service.ask_repo(
            repository_id=repo_id,
            question=question,
            top_k=payload.top_k,
        )
    except Exception as e:
        logger.error(f"AskRepo API Crash: {e}")
        # Return a safe, grounded error response instead of 500
        return AskRepoResponse(
            question=question,
            answer="The repository intelligence system encountered an internal error for this query. Please retry with a slightly simpler wording.",
            citations=[],
            mode="error",
            confidence="low",
            query_type="error",
            answer_mode="general",
            llm_model=None,
            snippet_found=False,
            notes=[str(e)]
        )

    return AskRepoResponse(
        question=question,
        answer=result.get("answer") or "I couldn't find enough relevant indexed context to answer that confidently. Try asking about a specific file, function, or line.",
        citations=result.get("citations") or [],
        mode=result.get("mode", "general"),
        llm_model=result.get("llm_model"),
        confidence=result.get("confidence", "low"),
        notes=result.get("notes") or [],
        query_type=result.get("query_type", "general"),
        answer_mode=result.get("answer_mode", "general"),
        snippet_found=result.get("snippet_found", False),
        # Line-level resolution fields
        resolved_file=result.get("resolved_file"),
        resolved_line_number=result.get("resolved_line_number"),
        matched_line=result.get("matched_line"),
        enclosing_scope=result.get("enclosing_scope"),
        line_type=result.get("line_type"),
    )


@router.get("/repos/{repo_id}/chunks", response_model=EmbeddingChunkListResponse)
def list_repository_chunks(
    repo_id: str,
    file_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    repository_service = RepositoryService(db)
    repository = repository_service.get_repository(repo_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    embedding_service = EmbeddingService(db)
    items, total = embedding_service.list_chunks(
        repository_id=repo_id,
        file_id=file_id,
        limit=limit,
        offset=offset,
    )

    response_items = [
        EmbeddingChunkItem(
            id=item.id,
            repository_id=item.repository_id,
            file_id=item.file_id,
            chunk_type=item.chunk_type,
            content=item.content,
            start_line=item.start_line,
            end_line=item.end_line,
            embedding_model=item.embedding_model,
            created_at=item.created_at,
        )
        for item in items
    ]

    return EmbeddingChunkListResponse(items=response_items, total=total)
