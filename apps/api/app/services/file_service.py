import re
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models.file import File

# ---------------------------------------------------------------------------
# Paths/extensions that are ALWAYS junk — generated, compiled, or OS noise
# ---------------------------------------------------------------------------
_JUNK_DIRS = {
    "node_modules", "__pycache__", ".git", ".next", ".nuxt", ".svelte-kit",
    "dist", "build", "out", "coverage", ".cache", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache", "target",
    "vendor", ".gradle", ".m2", "cmake-build-debug", "cmake-build-release",
}

_JUNK_EXTENSIONS = {
    # Compiled artifacts
    ".pyc", ".pyo", ".pyd", ".class", ".o", ".so", ".dll", ".exe", ".lib",
    ".a", ".dylib", ".obj", ".wasm",
    # Archives / binaries that are pure noise
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".rar", ".7z",
    # OS junk
    ".DS_Store",
}

_JUNK_FILENAMES = {
    ".DS_Store", "Thumbs.db", "desktop.ini", ".gitkeep",
}


def _is_junk_path(path: str) -> bool:
    """Returns True if the file path is clearly generated/vendor/OS junk."""
    parts = path.replace("\\", "/").split("/")
    # Any directory segment matches a known junk dir
    for part in parts[:-1]:
        if part in _JUNK_DIRS or part.startswith(".") and part not in (
            ".github", ".env", ".env.example", ".vscode", ".editorconfig",
            ".gitignore", ".gitattributes", ".eslintrc", ".prettierrc",
            ".babelrc", ".dockerignore",
        ):
            # Allow hidden config files/dirs, block hidden cache dirs
            if part.startswith(".") and part not in (
                ".github", ".vscode", ".devcontainer",
            ):
                pass  # allow .github, .vscode by not returning True
    
    # More surgical: only block the known-bad dir names
    for part in parts[:-1]:
        if part in _JUNK_DIRS:
            return True

    # Check extension
    filename = parts[-1]
    _, ext = (filename.rsplit(".", 1) if "." in filename else (filename, ""))
    if f".{ext.lower()}" in _JUNK_EXTENSIONS:
        return True
    if filename in _JUNK_FILENAMES:
        return True

    return False


class FileService:
    def __init__(self, db: Session):
        self.db = db

    def list_files(self, repository_id: str, limit: int = 500) -> list[dict]:
        """
        Returns all repository files that are real project assets.
        USE RAW SQL for the hotfix to bypass ANY ORM/schema mismatch.
        """
        try:
            stmt = text("""
                SELECT id, path, language, file_kind, line_count, parse_status 
                FROM files 
                WHERE repository_id = :rid 
                ORDER BY path ASC 
                LIMIT :limit
            """)
            result = self.db.execute(stmt, {"rid": repository_id, "limit": limit * 3})
            # Convert to list of dicts immediately
            rows = [dict(row._mapping) for row in result]
        except Exception:
            import logging
            logging.getLogger(__name__).warning("Raw SQL file listing failed", exc_info=True)
            return []

        # Apply path-based junk filter in Python
        visible = [f for f in rows if not _is_junk_path(f.get("path", ""))]
        return visible[:limit]

    def get_file(self, repository_id: str, file_id: str) -> File | None:
        return self.db.scalar(
            select(File).where(
                File.repository_id == repository_id,
                File.id == file_id,
            )
        )
