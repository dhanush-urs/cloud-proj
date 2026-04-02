from pathlib import Path


FRAMEWORK_SIGNATURES = {
    "FastAPI": ["requirements.txt", "pyproject.toml"],
    "Django": ["manage.py", "requirements.txt", "pyproject.toml"],
    "Flask": ["requirements.txt", "pyproject.toml"],
    "Next.js": ["next.config.js", "next.config.ts", "package.json"],
    "React": ["package.json"],
    "Express": ["package.json"],
    "NestJS": ["package.json"],
    "Spring Boot": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "Maven": ["pom.xml"],
    "Gradle": ["build.gradle", "build.gradle.kts"],
    "Go Modules": ["go.mod"],
    "Rust Cargo": ["Cargo.toml"],
    "Docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
    "Kubernetes": [".yaml", ".yml"],
}


def detect_frameworks(repo_root: Path) -> list[str]:
    detected = set()

    file_names = set()
    yaml_paths = []

    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue

        file_names.add(path.name)

        if path.suffix.lower() in {".yml", ".yaml"}:
            yaml_paths.append(path)

    # broad file-based detection
    for framework, signatures in FRAMEWORK_SIGNATURES.items():
        for signature in signatures:
            if signature.startswith("."):
                # suffix-based rule for YAML, handled later
                continue
            if signature in file_names:
                detected.add(framework)

    # content-based package.json detection
    package_json = repo_root / "package.json"
    if package_json.exists():
        try:
            content = package_json.read_text(encoding="utf-8", errors="ignore").lower()

            if "\"next\"" in content:
                detected.add("Next.js")
            if "\"react\"" in content:
                detected.add("React")
            if "\"express\"" in content:
                detected.add("Express")
            if "\"@nestjs/core\"" in content:
                detected.add("NestJS")
        except Exception:
            pass

    # Python framework detection
    for py_file in ["requirements.txt", "pyproject.toml"]:
        path = repo_root / py_file
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8", errors="ignore").lower()
                if "fastapi" in content:
                    detected.add("FastAPI")
                if "django" in content:
                    detected.add("Django")
                if "flask" in content:
                    detected.add("Flask")
            except Exception:
                pass

    # Kubernetes heuristic
    for yaml_file in yaml_paths[:50]:
        try:
            content = yaml_file.read_text(encoding="utf-8", errors="ignore").lower()
            if "apiversion:" in content and "kind:" in content:
                detected.add("Kubernetes")
                break
        except Exception:
            continue

    return sorted(detected)
