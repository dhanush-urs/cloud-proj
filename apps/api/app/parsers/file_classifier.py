from pathlib import Path


DOC_EXTENSIONS = {".md", ".mdx", ".txt", ".rst"}
CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env"}
SCRIPT_EXTENSIONS = {".sh", ".bash", ".zsh", ".ps1"}
ASSET_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".mp4", ".mp3", ".wav", ".pdf", ".woff", ".woff2", ".ttf",
}

CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".kt", ".kts", ".scala", ".sql",
}

BUILD_FILES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Makefile",
    "Jenkinsfile",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "go.mod",
    "Cargo.toml",
    "package.json",
    "pnpm-lock.yaml",
    "package-lock.json",
    "yarn.lock",
    "requirements.txt",
    "pyproject.toml",
}


def is_test_file(path: Path) -> bool:
    normalized = str(path).lower()

    test_markers = [
        "/test/",
        "/tests/",
        "\\test\\",
        "\\tests\\",
        "test_",
        "_test.py",
        ".spec.",
        ".test.",
    ]

    filename = path.name.lower()

    if filename.startswith("test_"):
        return True
    if filename.endswith("_test.py"):
        return True
    if ".spec." in filename or ".test." in filename:
        return True

    return any(marker in normalized for marker in test_markers)


def is_vendor_file(path: Path) -> bool:
    normalized_parts = {part.lower() for part in path.parts}

    vendor_dirs = {
        "node_modules",
        "vendor",
        "dist",
        "build",
        ".next",
        "coverage",
        "target",
        ".gradle",
        "__pycache__",
        ".venv",
        "venv",
    }

    if normalized_parts & vendor_dirs:
        return True

    filename = path.name.lower()

    if filename.endswith(".min.js") or filename.endswith(".min.css"):
        return True

    return False


def is_generated_file(path: Path) -> bool:
    filename = path.name.lower()

    generated_markers = [
        ".generated.",
        "_generated.",
        "generated_",
        ".pb.go",
        ".designer.cs",
    ]

    if any(marker in filename for marker in generated_markers):
        return True

    if filename.endswith(".min.js") or filename.endswith(".min.css"):
        return True

    return False


def classify_file(path: Path) -> dict:
    suffix = path.suffix.lower()
    filename = path.name

    test_flag = is_test_file(path)
    vendor_flag = is_vendor_file(path)
    generated_flag = is_generated_file(path)

    is_doc = suffix in DOC_EXTENSIONS or filename.lower() in {"readme", "readme.md", "license", "changelog.md"}
    is_config = suffix in CONFIG_EXTENSIONS or filename in BUILD_FILES or filename.startswith(".env")

    if filename in BUILD_FILES:
        file_kind = "build"
    elif test_flag:
        file_kind = "test"
    elif is_doc:
        file_kind = "doc"
    elif is_config:
        file_kind = "config"
    elif suffix in SCRIPT_EXTENSIONS:
        file_kind = "script"
    elif suffix in ASSET_EXTENSIONS:
        file_kind = "asset"
    elif suffix in CODE_EXTENSIONS or filename in {"Dockerfile"}:
        file_kind = "source"
    else:
        file_kind = "unknown"

    return {
        "file_kind": file_kind,
        "is_test": test_flag,
        "is_config": is_config,
        "is_doc": is_doc,
        "is_vendor": vendor_flag,
        "is_generated": generated_flag,
    }
