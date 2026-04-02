from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.files import FileDetailResponse, FileItem, FileListResponse
from app.services.file_service import FileService
from app.services.repository_service import RepositoryService

router = APIRouter(tags=["files"])


@router.get("/repos/{repo_id}/files", response_model=FileListResponse)
def list_repository_files(
    repo_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    repository_service = RepositoryService(db)
    repository = repository_service.get_repository(repo_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    file_service = FileService(db)
    files = file_service.list_files(repository_id=repo_id, limit=limit)

    return FileListResponse(
        repository_id=repo_id,
        total=len(files),
        items=[
            FileItem(
                id=f.id,
                path=f.path,
                language=f.language,
                file_kind=f.file_kind,
                line_count=f.line_count,
                parse_status=f.parse_status,
            )
            for f in files
        ],
    )


@router.get("/repos/{repo_id}/files/{file_id}", response_model=FileDetailResponse)
def get_repository_file_detail(
    repo_id: str,
    file_id: str,
    db: Session = Depends(get_db),
):
    repository_service = RepositoryService(db)
    repository = repository_service.get_repository(repo_id)

    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    file_service = FileService(db)
    file = file_service.get_file(repository_id=repo_id, file_id=file_id)

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    content = file.content
    if not content:
        from sqlalchemy import select
        from app.db.models.embedding_chunk import EmbeddingChunk
        chunks = db.scalars(
            select(EmbeddingChunk)
            .where(EmbeddingChunk.file_id == file_id)
            .order_by(EmbeddingChunk.start_line.asc())
        ).all()
        
        if chunks:
            content = "\n\n...[Chunk Boundary]...\n\n".join([c.content for c in chunks if c.content])

    return FileDetailResponse(
        id=file.id,
        repository_id=file.repository_id,
        path=file.path,
        language=file.language,
        file_kind=file.file_kind,
        line_count=file.line_count,
        parse_status=file.parse_status,
        is_generated=file.is_generated,
        is_vendor=file.is_vendor,
        content=content,
    )
