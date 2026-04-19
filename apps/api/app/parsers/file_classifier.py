from pathlib import Path


# ── Extension sets ──────────────────────────────────────────────────────────

DOC_EXTENSIONS = {".md", ".mdx", ".txt", ".rst", ".adoc"}

CONFIG_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".env", ".properties", ".conf", ".hcl", ".tf",
}

LOCK_EXTENSIONS = {".lock"}

SCRIPT_EXTENSIONS = {".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat"}

TEMPLATE_EXTENSIONS = {
    ".html", ".htm",
    ".ejs", ".hbs", ".handlebars", ".pug", ".jinja", ".jinja2",
    ".njk", ".liquid", ".mustache", ".twig",
}

STYLE_EXTENSIONS = {".css", ".scss", ".sass", ".less"}

DATA_EXTENSIONS = {".csv", ".tsv", ".sql", ".xml", ".graphql", ".gql", ".proto", ".prisma"}

ASSET_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".mp4", ".mp3", ".wav", ".ogg",
    ".pdf", ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".gz", ".tgz",
}

CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".rb", ".php", ".swift", ".kt", ".kts", ".scala",
    ".svg",  # SVG is technically markup/data but treat as source-like
}

# Named files that are always "build" regardless of extension
BUILD_FILES = {
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "Makefile", "Jenkinsfile", "Procfile", "Caddyfile", "Vagrantfile",
    "pom.xml", "build.gradle", "build.gradle.kts",
    "go.mod", "go.sum",
    "Cargo.toml", "Cargo.lock",
    "package.json", "package-lock.json",
    "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
    "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "Pipfile", "Pipfile.lock", "poetry.lock",
    "Gemfile", "Gemfile.lock", "composer.json", "composer.lock",
    "vite.config.ts", "vite.config.js",
    "next.config.ts", "next.config.js", "next.config.mjs",
    "tsconfig.json", "jsconfig.json",
    ".gitignore", ".dockerignore", ".nvmrc", ".node-version",
}

# Named files that are config
CONFIG_FILES = {
    ".env", ".env.example", ".env.local", ".env.production",
    ".env.development", ".env.test", ".env.staging",
    ".editorconfig", ".prettierrc", ".eslintrc", ".babelrc",
    ".eslintignore", ".prettierignore",
    "CODEOWNERS", "renovate.json",
}

# Named files that are docs
DOC_FILES = {
    "README", "README.md", "README.rst", "README.txt",
    "CHANGELOG", "CHANGELOG.md", "CHANGES", "HISTORY",
    "LICENSE", "LICENCE", "NOTICE", "COPYING",
    "AUTHORS", "CONTRIBUTORS", "HACKING", "TODO",
}


# ── Classifier helpers ──────────────────────────────────────────────────────

def is_test_file(path: Path) -> bool:
    normalized = str(path).lower()
    filename = path.name.lower()
    if filename.startswith("test_") or filename.endswith("_test.py"):
        return True
    if ".spec." in filename or ".test." in filename:
        return True
    return any(m in normalized for m in ("/test/", "/tests/", "\\test\\", "\\tests\\"))


def is_vendor_file(path: Path) -> bool:
    vendor_dirs = {
        "node_modules", "vendor", "dist", "build", "out",
        ".next", ".nuxt", ".svelte-kit", "coverage", "target",
        ".gradle", "__pycache__", ".venv", "venv", "env",
    }
    if {part.lower() for part in path.parts} & vendor_dirs:
        return True
    filename = path.name.lower()
    return filename.endswith(".min.js") or filename.endswith(".min.css")


def is_generated_file(path: Path) -> bool:
    filename = path.name.lower()
    generated_markers = [
        ".generated.", "_generated.", "generated_",
        ".pb.go", ".designer.cs",
    ]
    if any(m in filename for m in generated_markers):
        return True
    return filename.endswith(".min.js") or filename.endswith(".min.css")


# ── Main classifier ─────────────────────────────────────────────────────────

def classify_file(path: Path) -> dict:
    suffix = path.suffix.lower()
    filename = path.name

    test_flag = is_test_file(path)
    vendor_flag = is_vendor_file(path)
    generated_flag = is_generated_file(path)

    is_doc = (
        suffix in DOC_EXTENSIONS
        or filename in DOC_FILES
        or filename.lower() in {"readme", "license", "changelog"}
    )
    is_config = (
        suffix in CONFIG_EXTENSIONS
        or suffix in LOCK_EXTENSIONS
        or filename in CONFIG_FILES
        or filename.startswith(".env")
    )

    # Determine file_kind — first-match priority
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
    elif suffix in TEMPLATE_EXTENSIONS:
        file_kind = "markup"
    elif suffix in STYLE_EXTENSIONS:
        file_kind = "style"
    elif suffix in DATA_EXTENSIONS:
        file_kind = "data"
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
