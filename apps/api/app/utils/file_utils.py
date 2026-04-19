from pathlib import Path


# Directories that are always generated/vendor/cache — never walk into them
IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".next",
    ".nuxt",
    ".svelte-kit",
    "dist",
    "build",
    "out",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".turbo",
    ".gradle",
    ".m2",
    "target",
    "coverage",
    ".tox",
    "cmake-build-debug",
    "cmake-build-release",
}

# All extensions we can safely read as UTF-8 text and store as content
TEXT_EXTENSIONS = {
    # Source code
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".rb", ".php", ".swift", ".kt", ".kts", ".scala",
    # Web / templates
    ".html", ".htm",
    ".css", ".scss", ".sass", ".less",
    ".ejs", ".hbs", ".handlebars", ".pug", ".jinja", ".jinja2",
    ".njk", ".liquid", ".mustache", ".twig",
    # Config / data
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".env", ".env.example", ".env.local", ".env.production",
    ".xml", ".csv", ".tsv", ".sql",
    # Docs
    ".md", ".mdx", ".rst", ".txt", ".adoc",
    # Scripts / shell
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat",
    # Infra / build
    ".dockerfile", ".tf", ".hcl",
    ".graphql", ".gql", ".prisma", ".proto",
    # Lock / manifest (text-based)
    ".lock",
    # Misc text
    ".svg", ".gitignore", ".dockerignore",
    ".prettierrc", ".eslintrc", ".babelrc",
    ".editorconfig", ".nvmrc",
}

# Named files that are text but have no extension or non-standard extensions
TEXT_NAMED_FILES = {
    "Dockerfile", "Makefile", "Jenkinsfile", "Procfile", "Gemfile",
    ".gitignore", ".dockerignore", ".env", ".editorconfig", ".nvmrc",
    "Pipfile", "Brewfile", "Caddyfile", "Vagrantfile",
    "yarn.lock", "poetry.lock", "Pipfile.lock", "Gemfile.lock",
    "go.sum", "cargo.lock", "composer.lock",
    "CODEOWNERS", "OWNERS", "AUTHORS", "CONTRIBUTORS",
    "LICENSE", "LICENCE", "NOTICE", "COPYING",
    "README", "CHANGELOG", "CHANGES", "HISTORY", "TODO", "HACKING",
}


def should_ignore_dir(path: Path) -> bool:
    return path.name in IGNORED_DIRS


def iter_repo_files(repo_root: Path):
    """Recursively yield all non-ignored files under repo_root."""
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        # Skip if any ancestor directory is in the ignore list
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        yield path


def safe_read_text(path: Path, max_bytes: int = 2_000_000) -> str:
    """Read a text file safely, returning empty string on failure or oversized files."""
    if not path.exists() or not path.is_file():
        return ""
    try:
        size = path.stat().st_size
    except OSError:
        return ""
    if size == 0:
        return ""
    if size > max_bytes:
        # For large files, read first max_bytes only (still useful for embedding)
        try:
            with path.open("rb") as f:
                raw = f.read(max_bytes)
            return raw.decode("utf-8", errors="ignore")
        except Exception:
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
    """Return True if this file is likely human-readable text we should store."""
    # Named files with no or unusual extension
    if path.name in TEXT_NAMED_FILES:
        return True
    # Files whose name starts with a dot and matches a known config
    if path.name.startswith(".env"):
        return True
    # Extension-based check
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    return False
