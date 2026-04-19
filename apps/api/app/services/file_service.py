import re
from sqlalchemy import select
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

    def list_files(self, repository_id: str, limit: int = 500) -> list[File]:
        """
        Returns all repository files that are real project assets.
        Hides only generated/vendor/compiled/OS junk.
        Does NOT require text content or line_count > 0 —
        binary assets and templates are valid repo files.
        """
        rows = list(
            self.db.scalars(
                select(File)
                .where(File.repository_id == repository_id)
                .order_by(File.path.asc())
                .limit(limit * 3)  # over-fetch to allow client-side junk filter
            ).all()
        )
        # Apply path-based junk filter in Python (avoids SQL LIKE complexity)
        visible = [f for f in rows if not _is_junk_path(f.path)]
        return visible[:limit]

    def get_file(self, repository_id: str, file_id: str) -> File | None:
        return self.db.scalar(
            select(File).where(
                File.repository_id == repository_id,
                File.id == file_id,
            )
        )
