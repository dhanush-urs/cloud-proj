import json
import re
from pathlib import Path

# Framework detection rules
# Requires (Manifest Dependency) AND (Usage Signal).
FRAMEWORK_RULES = {
    "FastAPI": {
        "deps": ["fastapi", "pydantic", "starlette"],
        "patterns": [r"from fastapi import", r"import fastapi", r"FastAPI\("],
        "files": ["main.py", "app.py", "asgi.py", "router.py"]
    },
    "Django": {
        "deps": ["django"],
        "patterns": [r"from django", r"import django"],
        "files": ["manage.py", "settings.py", "wsgi.py"]
    },
    "Flask": {
        "deps": ["flask"],
        "patterns": [r"from flask import Flask", r"import flask", r"Flask\("],
        "files": ["app.py", "wsgi.py"]
    },
    "Next.js": {
        "deps": ["next", "react-dom"],
        "files": ["next.config.js", "next.config.ts", "next.config.mjs", "app/layout.tsx", "pages/_app.tsx", "tailwind.config.ts"],
        "patterns": [r"from 'next/", r"from \"next/", r"export default nextConfig"]
    },
    "React": {
        "deps": ["react"],
        "patterns": [r"import React", r"from 'react'", r'from "react"', r"import {.*} from 'react'"],
        "extensions": [".tsx", ".jsx"]
    },
    "Vue": {
        "deps": ["vue"],
        "extensions": [".vue"],
        "patterns": [r"from 'vue'", r"from \"vue\""]
    },
    "Svelte": {
        "deps": ["svelte"],
        "extensions": [".svelte"]
    },
    "Astro": {
        "deps": ["astro"],
        "extensions": [".astro"],
        "files": ["astro.config.mjs", "astro.config.ts"]
    },
    "Tailwind CSS": {
        "deps": ["tailwindcss"],
        "files": ["tailwind.config.js", "tailwind.config.ts", "tailwind.config.cjs"],
        "patterns": [r"@tailwind base", r"@tailwind components", r"@tailwind utilities"]
    },
    "Spring Boot": {
        "deps": ["spring-boot-starter"],
        "patterns": [r"@SpringBootApplication", r"import org\.springframework"],
        "extensions": [".java", ".kt"]
    },
    "Electron": {
        "deps": ["electron"],
        "patterns": [r"BrowserWindow\(", r"app\.on\("]
    },
    "Celery": {
        "deps": ["celery"],
        "patterns": [r"Celery\(", r"@.*\.task", r"CELERY_BROKER", r"celery_app"],
        "files": ["celery.py", "celery_app.py", "tasks.py"]
    },
    "Redis": {
        "deps": ["redis", "ioredis"],
        "patterns": [r"Redis\(", r"redis\.", r"REDIS_URL"]
    },
    "Postgres": {
        "deps": ["psycopg2", "asyncpg", "pg", "sequelize", "typeorm"],
        "patterns": [r"postgresql://", r"postgres://", r"PostgreSQL"]
    },
    "Neo4j": {
        "deps": ["neo4j", "neo4j-driver"],
        "patterns": [r"bolt://", r"neo4j://", r"neo4j\."]
    },
}

# Frameworks that qualify with EITHER dependency OR usage (Infra/DB)
INFRA_FRAMEWORKS = {"Postgres", "Redis", "Neo4j", "Celery", "Docker", "Kubernetes"}

def _scan_files(repo_root: Path) -> list[Path]:
    """Gather up to 3 levels of files for analysis (supports monorepos)."""
    found = []
    ignored = {"node_modules", ".git", "venv", ".venv", "dist", "build", ".next", "__pycache__"}
    if not repo_root.exists():
        return found
    
    def _walk(current_path: Path, depth: int):
        if depth > 5:
            return
        try:
            for p in current_path.iterdir():
                if p.name in ignored:
                    continue
                if p.is_file():
                    found.append(p)
                elif p.is_dir():
                    _walk(p, depth + 1)
        except:
            pass

    _walk(repo_root, 1)
    return found

def detect_frameworks(repo_root: Path) -> list[str]:
    """
    Detects frameworks with strict evidence thresholds.
    Ensures that a framework is only reported if it's actually used, not just mentioned.
    """
    detected = set()
    
    try:
        all_files = _scan_files(repo_root)
    except Exception:
        return []
        
    file_names = {p.name for p in all_files}
    extensions = {p.suffix.lower() for p in all_files}
    
    # 1. Gather Dependencies from All Discovered Manifests (Monorepo Support)
    all_deps = set()
    
    # Manifest patterns to check
    manifest_files = [f for f in all_files if f.name in {
        "package.json", "requirements.txt", "pyproject.toml", "Pipfile",
        "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts"
    }]
    
    for manifest_path in manifest_files:
        filename = manifest_path.name
        try:
            content = manifest_path.read_text(errors="ignore")
            
            if filename == "package.json":
                try:
                    data = json.loads(content)
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    all_deps.update(deps.keys())
                except: pass
            
            else:
                # Text-based manifests (requirements.txt, pom.xml, gradle, go.mod, etc.)
                content_lower = content.lower()
                for framework_name, rule in FRAMEWORK_RULES.items():
                    for d in rule.get("deps", []):
                        if d.lower() in content_lower:
                            all_deps.add(d)
        except Exception as e:
            logger.warning(f"Failed to scan manifest {manifest_path}: {e}")


    # 2. Check each framework rule
    for name, rule in FRAMEWORK_RULES.items():
        # A framework must have a dependency in manifest...
        has_dep = any(d in all_deps for d in rule.get("deps", []))
        
        # ...AND some form of usage evidence
        has_usage = False
        
        # Evidence type A: Specialized file existence (e.g. manage.py, next.config.js)
        if any(f in file_names for f in rule.get("files", [])):
            has_usage = True
        
        # Evidence type B: Language/Extension direct binding (e.g. .vue, .tsx)
        if not has_usage and any(ext in extensions for ext in rule.get("extensions", [])):
            has_usage = True
            
        # Evidence type C: Code pattern scanning (imports, instantiation)
        if not has_usage and "patterns" in rule:
            compiled = [re.compile(p) for p in rule["patterns"]]
            count = 0
            for p in all_files:
                # Only scan likely source files
                if p.suffix in {".py", ".js", ".ts", ".tsx", ".jsx"} and p.stat().st_size < 100000:
                    try:
                        content = p.read_text(errors="ignore")
                        if any(pat.search(content) for pat in compiled):
                            has_usage = True
                            break
                    except: pass
                    count += 1
                    if count >= 15: break # Cap scan for performance

        is_infra = name in INFRA_FRAMEWORKS
        # Stricter infra check: must have dependency AND usage if it's infra
        # Otherwise we get hallucinations from packages that are installed but unused (e.g. sequelize for a JSON-only app)
        if (has_dep and has_usage):
            detected.add(name)
        elif is_infra and has_usage:
            # If it's infra (Postgres/Redis), we can accept usage even skip dep (e.g. system db)
            # but we MUST NOT accept dep-only (no usage) as that's usually a false positive.
            detected.add(name)
            
    # 3. Infrastructure & Language Modules (Scan all discovered file names/paths)
    all_rel_paths = {str(p.relative_to(repo_root)) for p in all_files}
    all_filenames = {p.name for p in all_files}

    if any(df in all_filenames for df in ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"]):
        detected.add("Docker")
    if "go.mod" in all_filenames: detected.add("Go Modules")
    if "Cargo.toml" in all_filenames: detected.add("Rust Cargo")
    
    # K8s detection via file content sampling
    for f in all_files:
        if f.suffix in {".yaml", ".yml"}:
            try:
                sample = f.read_text(errors="ignore")[:1000].lower()
                if "apiversion:" in sample:
                    detected.add("Kubernetes")
                    break
            except: pass

    # 4. Result Synthesis & Static Fallback
    # Filter out noisy or redundant infrastructure names if major frameworks are present
    res = sorted(list(detected))
    if not res:
        # Check if it has web files to qualify as Static
        if any(ext in extensions for ext in {".html", ".css", ".js"}):
            return ["Static HTML/CSS/JavaScript"]
        return []
        
    return res
