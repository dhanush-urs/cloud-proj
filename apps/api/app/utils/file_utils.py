from pathlib import Path


IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".turbo",
    ".gradle",
    "target",
    "coverage",
}

TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".kts",
    ".scala",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".md",
    ".txt",
    ".sh",
    ".sql",
    ".dockerfile",
}


def should_ignore_dir(path: Path) -> bool:
    return path.name in IGNORED_DIRS


def iter_repo_files(repo_root: Path):
    for path in repo_root.rglob("*"):
        if path.is_dir():
            if should_ignore_dir(path):
                continue
            continue

        if any(part in IGNORED_DIRS for part in path.parts):
            continue

        yield path


def safe_read_text(path: Path, max_bytes: int = 1_000_000) -> str:
    if not path.exists() or not path.is_file():
        return ""

    if path.stat().st_size > max_bytes:
        return ""

    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def count_lines(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + 1


def is_probably_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True

    if path.name in {"Dockerfile", "Makefile", "Jenkinsfile"}:
        return True

    return False
