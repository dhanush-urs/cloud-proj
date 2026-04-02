from collections import Counter
from pathlib import Path

from app.utils.file_utils import iter_repo_files

EXTENSION_LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".sh": "Shell",
    ".sql": "SQL",
}


def detect_file_language(path: Path) -> str | None:
    if path.name == "Dockerfile":
        return "Dockerfile"

    suffix = path.suffix.lower()
    return EXTENSION_LANGUAGE_MAP.get(suffix)


def detect_languages(repo_root: Path) -> dict:
    counter = Counter()

    for path in iter_repo_files(repo_root):
        if not path.is_file():
            continue

        language = detect_file_language(path)
        if language:
            counter[language] += 1

    total = sum(counter.values())
    primary_language = counter.most_common(1)[0][0] if counter else None

    return {
        "primary_language": primary_language,
        "language_counts": dict(counter),
        "total_detected_code_files": total,
    }
