from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
import mimetypes
import os
import hashlib
import shutil
import subprocess
from pathlib import Path

from app.api.deps import get_db
from app.schemas.files import FileDetailResponse, FileItem, FileListResponse
from app.services.file_service import FileService
from app.services.repository_service import RepositoryService

router = APIRouter(tags=["files"])

# ---------------------------------------------------------------------------
# MIME type table — covers types that Python's mimetypes module misses on
# minimal Linux images (Alpine, Debian-slim, etc.)
# ---------------------------------------------------------------------------
_EXTRA_MIME: dict[str, str] = {
    # Office Open XML
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt":  "application/vnd.ms-powerpoint",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc":  "application/msword",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls":  "application/vnd.ms-excel",
    # OpenDocument
    ".odp":  "application/vnd.oasis.opendocument.presentation",
    ".odt":  "application/vnd.oasis.opendocument.text",
    ".ods":  "application/vnd.oasis.opendocument.spreadsheet",
    # PDF
    ".pdf":  "application/pdf",
    # Images
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif":  "image/gif",
    ".webp": "image/webp",
    ".svg":  "image/svg+xml",
    ".ico":  "image/x-icon",
    # Archives
    ".zip":  "application/zip",
    ".tar":  "application/x-tar",
    ".gz":   "application/gzip",
    ".tgz":  "application/gzip",
    ".bz2":  "application/x-bzip2",
    ".7z":   "application/x-7z-compressed",
    ".rar":  "application/vnd.rar",
    # Fonts
    ".ttf":  "font/ttf",
    ".otf":  "font/otf",
    ".woff": "font/woff",
    ".woff2":"font/woff2",
    # Data / config (browser-renderable as text)
    ".json": "application/json",
    ".xml":  "application/xml",
    ".yaml": "text/yaml",
    ".yml":  "text/yaml",
    ".toml": "text/plain",
    ".csv":  "text/csv",
    # Code / text — explicit so they always render inline
    ".md":   "text/markdown",
    ".txt":  "text/plain",
    ".html": "text/html",
    ".htm":  "text/html",
    ".css":  "text/css",
    ".js":   "text/javascript",
    ".ts":   "text/typescript",
    ".py":   "text/x-python",
    ".sh":   "text/x-sh",
    ".sql":  "text/x-sql",
}

# Extensions the browser can render inline without issues
_INLINE_EXTENSIONS: frozenset[str] = frozenset({
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    ".txt", ".md", ".html", ".htm", ".css", ".js", ".ts",
    ".json", ".xml", ".yaml", ".yml", ".csv", ".py", ".sh",
    ".sql", ".toml", ".rs", ".go", ".java", ".rb", ".php",
    ".c", ".cpp", ".h", ".cs", ".swift", ".kt", ".r",
})

_PPT_EXTENSIONS = {".ppt", ".pptx"}
_PREVIEW_CACHE_ROOT = Path(os.getenv("REPOBRAIN_PREVIEW_CACHE_DIR", "/tmp/repobrain-preview-cache"))


def _resolve_mime(path: str) -> tuple[str, str]:
    """
    Return (media_type, content_disposition_type) for a file path.

    - Known binary formats that browsers cannot render get 'attachment' so the
      browser downloads them instead of trying to display raw bytes.
    - Text / browser-renderable formats get 'inline'.
    - Unknown extensions fall back to application/octet-stream + attachment.
    """
    _, ext = os.path.splitext(path.lower())

    # 1. Check our explicit table first (most reliable)
    media_type = _EXTRA_MIME.get(ext)

    # 2. Fall back to Python's mimetypes module
    if not media_type:
        guessed, _ = mimetypes.guess_type(path)
        media_type = guessed

    # 3. Final fallback — safe binary download
    if not media_type:
        media_type = "application/octet-stream"

    # Decide inline vs attachment
    if ext in _INLINE_EXTENSIONS:
        disposition = "inline"
    else:
        disposition = "attachment"

    return media_type, disposition


def _resolve_repo_file_path(repository, relative_path: str) -> str | None:
    if not repository.local_path:
        return None
    full_path = os.path.join(repository.local_path, relative_path)
    real_repo_dir = os.path.realpath(repository.local_path)
    try:
        real_file_path = os.path.realpath(full_path)
    except Exception:
        return None

    if (
        real_file_path
        and real_file_path.startswith(real_repo_dir + os.sep)
        and os.path.isfile(real_file_path)
    ):
        return real_file_path
    return None


def _preview_cache_key(source_path: str) -> str:
    stat = os.stat(source_path)
    material = f"{source_path}|{stat.st_mtime_ns}|{stat.st_size}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _convert_office_to_pdf_cached(source_path: str) -> tuple[str | None, str | None]:
    soffice_bin = shutil.which("soffice")
    if not soffice_bin:
        return None, "Inline preview is unavailable in this environment. LibreOffice is not installed."

    cache_key = _preview_cache_key(source_path)
    out_dir = _PREVIEW_CACHE_ROOT / cache_key
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = out_dir / "lo-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    out_pdf = out_dir / "preview.pdf"
    if out_pdf.exists() and out_pdf.stat().st_size > 0:
        return str(out_pdf), None

    cmd = [
        soffice_bin,
        "--headless",
        f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        source_path,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
            env={**os.environ, "HOME": str(out_dir)},
        )
    except subprocess.TimeoutExpired:
        return None, "Inline preview is unavailable in this environment. Office conversion timed out."
    except Exception:
        return None, "Inline preview is unavailable in this environment. Office conversion failed to start."

    if proc.returncode != 0:
        return None, "Inline preview is unavailable in this environment. Office conversion failed."

    converted = out_dir / (Path(source_path).stem + ".pdf")
    if converted.exists() and converted.stat().st_size > 0:
        if converted != out_pdf:
            converted.replace(out_pdf)
        return str(out_pdf), None
    return None, "Inline preview is unavailable in this environment. Office conversion produced no preview."


def _convert_office_to_image_cached(source_path: str) -> tuple[str | None, str | None]:
    soffice_bin = shutil.which("soffice")
    if not soffice_bin:
        return None, "Inline preview is unavailable in this environment. LibreOffice is not installed."

    cache_key = _preview_cache_key(source_path)
    out_dir = _PREVIEW_CACHE_ROOT / f"{cache_key}-img"
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = out_dir / "lo-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    png_candidates = sorted(out_dir.glob("*.png"))
    if png_candidates:
        return str(png_candidates[0]), None

    cmd = [
        soffice_bin,
        "--headless",
        f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
        "--convert-to",
        "png",
        "--outdir",
        str(out_dir),
        source_path,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
            env={**os.environ, "HOME": str(out_dir)},
        )
    except subprocess.TimeoutExpired:
        return None, "Inline preview is unavailable in this environment. Office image conversion timed out."
    except Exception:
        return None, "Inline preview is unavailable in this environment. Office image conversion failed to start."

    if proc.returncode != 0:
        return None, "Inline preview is unavailable in this environment. Office image conversion failed."

    png_candidates = sorted(out_dir.glob("*.png"))
    if png_candidates:
        return str(png_candidates[0]), None
    return None, "Inline preview is unavailable in this environment. Office image conversion produced no preview."


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
        status=repository.status,
        total=len(files),
        items=files,
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

    # Detect binary files by extension — use the same MIME table for consistency
    _, ext = os.path.splitext(file.path.lower())
    _text_prefixes = ("text/", "application/json", "application/xml")
    _resolved_mime, _ = _resolve_mime(file.path)
    is_binary = (
        not any(_resolved_mime.startswith(p) for p in _text_prefixes)
        or file.file_kind == "binary"
    )
    
    # Construct raw URL
    raw_url = f"/api/v1/repos/{repo_id}/files/{file_id}/raw"

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
        raw_url=raw_url,
        is_binary=is_binary,
    )


@router.get("/repos/{repo_id}/files/{file_id}/raw")
def get_repository_file_raw(
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

    media_type, disposition = _resolve_mime(file.path)

    # ── Path 1: serve from disk (preferred — preserves exact binary bytes) ──
    real_file_path = _resolve_repo_file_path(repository, file.path)
    if real_file_path:
        filename = os.path.basename(file.path)
        return FileResponse(
            real_file_path,
            media_type=media_type,
            content_disposition_type=disposition,
            filename=filename if disposition == "attachment" else None,
        )

    # ── Path 2: fall back to DB-stored text content ──────────────────────────
    # Binary files have no stored content, so this only helps text/code files
    # when the clone directory has been cleaned up.
    if file.content:
        text_media = media_type if media_type.startswith("text/") else "text/plain"
        filename = os.path.basename(file.path)
        headers = {
            "Content-Disposition": f'{disposition}; filename="{filename}"',
        }
        return Response(
            content=file.content.encode("utf-8", errors="replace"),
            media_type=text_media,
            headers=headers,
        )

    # ── Path 3: nothing available ─────────────────────────────────────────────
    raise HTTPException(
        status_code=404,
        detail=(
            "Raw file not available. The repository clone may have been removed. "
            "Re-index the repository to restore file access."
        ),
    )


@router.get("/repos/{repo_id}/files/{file_id}/preview")
def get_repository_file_preview(
    repo_id: str,
    file_id: str,
    metadata: bool = Query(default=False),
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

    source_path = _resolve_repo_file_path(repository, file.path)
    if not source_path:
        raise HTTPException(
            status_code=404,
            detail=(
                "Preview file is not available on disk. Re-index the repository to restore preview access."
            ),
        )

    _, ext = os.path.splitext(file.path.lower())

    # If already browser previewable, stream it directly.
    if ext in _INLINE_EXTENSIONS:
        media_type, _ = _resolve_mime(file.path)
        if metadata:
            return {
                "available": True,
                "media_type": media_type,
                "preview_url": f"/api/v1/repos/{repo_id}/files/{file_id}/preview",
                "message": None,
            }
        return FileResponse(
            source_path,
            media_type=media_type,
            content_disposition_type="inline",
        )

    # Office presentations: convert to PDF preview.
    if ext in _PPT_EXTENSIONS:
        preview_pdf, error_msg = _convert_office_to_pdf_cached(source_path)
        if preview_pdf:
            if metadata:
                return {
                    "available": True,
                    "media_type": "application/pdf",
                    "preview_url": f"/api/v1/repos/{repo_id}/files/{file_id}/preview",
                    "message": None,
                }
            return FileResponse(
                preview_pdf,
                media_type="application/pdf",
                content_disposition_type="inline",
            )
        preview_img, image_error = _convert_office_to_image_cached(source_path)
        if preview_img:
            if metadata:
                return {
                    "available": True,
                    "media_type": "image/png",
                    "preview_url": f"/api/v1/repos/{repo_id}/files/{file_id}/preview",
                    "message": None,
                }
            return FileResponse(
                preview_img,
                media_type="image/png",
                content_disposition_type="inline",
            )

        final_error = image_error or error_msg or "Inline preview is unavailable in this environment. You can still open the raw file."
        if metadata:
            return {
                "available": False,
                "media_type": None,
                "preview_url": None,
                "message": final_error,
            }
        raise HTTPException(status_code=503, detail=final_error)

    if metadata:
        return {
            "available": False,
            "media_type": None,
            "preview_url": None,
            "message": "Inline preview is unavailable for this file type. You can still open the raw file.",
        }
    raise HTTPException(
        status_code=415,
        detail="Inline preview is unavailable for this file type. You can still open the raw file.",
    )
