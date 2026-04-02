from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

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

router = APIRouter(tags=["search"])


@router.post("/repos/{repo_id}/embed", response_model=EmbedRepositoryResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_repository_embedding(
    repo_id: str,
    db: Session = Depends(get_db),
):
    repository_service = RepositoryService(db)
    repository = repository_service.get_repository(repo_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    if repository.status not in {"indexed", "parsed"}:
        raise HTTPException(
            status_code=400,
            detail="Repository must be indexed or parsed before embedding",
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

    task = embed_repository.delay(repo_id, job.id)
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
    repository_service = RepositoryService(db)
    repository = repository_service.get_repository(repo_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        rag_service = RAGService(db)
        result = rag_service.ask_repo(
            repository_id=repo_id,
            question=payload.question,
            top_k=payload.top_k,
        )
    except Exception as e:
        import logging, traceback
        logging.getLogger(__name__).error(f"Error in ask_repo: {str(e)}\n{traceback.format_exc()}")
        # FIX 6: Graceful fallback when Gemini is unavailable or RAG pipeline fails.
        # Always return a structured response — never 500.
        return AskRepoResponse(
            question=payload.question,
            answer="I couldn't produce a reliable grounded answer from the indexed repository context right now.",
            citations=[],
            mode="fallback",
            llm_model=None,
        )

    return AskRepoResponse(
        question=payload.question,
        answer=result["answer"],
        citations=result["citations"],
        mode=result["mode"],
        llm_model=result["llm_model"],
        confidence=result.get("confidence"),
        notes=result.get("notes", []),
        query_type=result.get("query_type"),
        answer_mode=result.get("answer_mode"),
        snippet_found=result.get("snippet_found"),
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
