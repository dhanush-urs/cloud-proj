import json
from pathlib import Path
from typing import Dict, Set

# Framework detection rules
# Sources: README mention, Direct Dependency (manifest), Entrypoint existence.
# Score thresholds: >= 3 to report.
FRAMEWORK_RULES = {
    "FastAPI": {
        "manifests": ["requirements.txt", "pyproject.toml", "Pipfile"],
        "entrypoints": ["main.py", "app.py", "asgi.py"],
        "deps": ["fastapi"],
    },
    "Django": {
        "manifests": ["requirements.txt", "pyproject.toml"],
        "entrypoints": ["manage.py", "wsgi.py", "asgi.py"],
        "deps": ["django"],
    },
    "Flask": {
        "manifests": ["requirements.txt", "pyproject.toml"],
        "entrypoints": ["app.py", "wsgi.py"],
        "deps": ["flask"],
    },
    "Next.js": {
        "manifests": ["package.json"],
        "entrypoints": ["next.config.js", "next.config.ts", "next.config.mjs"],
        "deps": ["next"],
    },
    "React": {
        "manifests": ["package.json"],
        "entrypoints": ["App.tsx", "App.jsx", "main.tsx", "main.jsx"],
        "deps": ["react"],
    },
    "Express": {
        "manifests": ["package.json"],
        "entrypoints": ["app.js", "server.js", "index.js"],
        "deps": ["express"],
    },
    "NestJS": {
        "manifests": ["package.json"],
        "entrypoints": ["main.ts"],
        "deps": ["@nestjs/core"],
    },
    "Spring Boot": {
        "manifests": ["pom.xml", "build.gradle", "build.gradle.kts"],
        "entrypoints": ["Application.java", "Application.kt"],
        "deps": ["spring-boot-starter"],
    },
    "Go Modules": {
        "manifests": ["go.mod"],
        "entrypoints": ["main.go"],
        "deps": [],
    },
    "Rust Cargo": {
        "manifests": ["Cargo.toml"],
        "entrypoints": ["main.rs", "lib.rs"],
        "deps": [],
    },
}

def _scan_files(repo_root: Path) -> Set[Path]:
    """Scan top-level and 1st-level subdirs for relevant files efficiently."""
    files = set()
    ignored = {"node_modules", "vendor", "dist", "build", ".next", ".git", "__pycache__", "venv", ".venv"}
    
    if not repo_root.exists():
        return files

    # Top level
    for p in repo_root.iterdir():
        if p.is_file():
            files.add(p)
        elif p.is_dir() and p.name not in ignored:
            # 1st level subdirs
            try:
                for sub_p in p.iterdir():
                    if sub_p.is_file():
                        files.add(sub_p)
            except (PermissionError, Exception):
                continue
    return files

def detect_frameworks(repo_root: Path) -> list[str]:
    """
    Detects frameworks with an evidence-based scoring hierarchy.
    Threshold: score >= 3 is reported.
    README (+3), Entrypoint (+3), Direct Dependency (+2).
    """
    scores: Dict[str, int] = {f: 0 for f in FRAMEWORK_RULES}
    
    try:
        all_files = _scan_files(repo_root)
    except Exception:
        return []
    
    file_names = {p.name for p in all_files}
    
    # 1. README check (+3) - Very strong signal
    readme = next((p for p in all_files if p.name.lower() == "readme.md"), None)
    if readme:
        try:
            content = readme.read_text(encoding="utf-8", errors="ignore").lower()
            for framework in FRAMEWORK_RULES:
                if framework.lower() in content:
                    scores[framework] += 3
        except Exception:
            pass

    # 2. Entrypoint check (+3) - Concrete evidence of runtime
    for framework, rules in FRAMEWORK_RULES.items():
        for ep in rules["entrypoints"]:
            if ep in file_names:
                scores[framework] += 3
                break

    # 3. Manifest / Dependency check (+2) - Medium signal
    package_json_path = repo_root / "package.json"
    if package_json_path.exists():
        try:
            with open(package_json_path, "r") as f:
                data = json.load(f)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                for framework, rules in FRAMEWORK_RULES.items():
                    if any(d in deps for d in rules["deps"]) and "package.json" in rules["manifests"]:
                        scores[framework] += 2
        except Exception:
            pass

    # Python Manifests
    for py_man in ["requirements.txt", "pyproject.toml"]:
        man_path = repo_root / py_man
        if man_path.exists():
            try:
                content = man_path.read_text(encoding="utf-8", errors="ignore").lower()
                for framework, rules in FRAMEWORK_RULES.items():
                    if py_man in rules["manifests"]:
                        if any(dep.lower() in content for dep in rules["deps"]):
                            scores[framework] += 2
            except Exception:
                pass

    # 4. Result Synthesis
    detected = [f for f, score in scores.items() if score >= 3]
    
    # Special cases for Infra/Common tools
    # Kubernetes Heuristic
    is_k8s = False
    for p in all_files:
        if p.suffix.lower() in {".yaml", ".yml"}:
            try:
                content = p.read_text(encoding="utf-8", errors="ignore").lower()
                # Check for Kubernetes-specific markers
                if "apiversion:" in content and "kind:" in content:
                    is_k8s = True
                    break
            except Exception:
                continue
    if is_k8s:
        detected.append("Kubernetes")
        
    # Docker Heuristic
    if any(df in file_names for df in ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"]):
        detected.append("Docker")

    return sorted(list(set(detected)))
