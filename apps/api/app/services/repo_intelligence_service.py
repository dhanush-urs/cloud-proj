"""RepoIntelligenceService — builds and persists full repo-wide memory artifacts.

Called during the parse pipeline (tasks_parse.py) after semantic analysis completes.
Produces a RepoIntelligence record that Ask Repo uses as its primary context
for repo_summary and architecture questions — replacing top-K chunk retrieval.
"""
from __future__ import annotations

import json
import logging
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.dependency_edge import DependencyEdge
from app.db.models.file import File
from app.db.models.repo_intelligence import RepoIntelligence
from app.db.models.repository import Repository
from app.db.models.symbol import Symbol
from app.llm.providers import get_chat_provider

logger = logging.getLogger(__name__)

# ── Paths to always exclude from intelligence building ─────────────────────────
IGNORED_PATH_PREFIXES = [
    "deployed_sites/",
    "node_modules/",
    "build/",
    "dist/",
    "out/",
    ".next/",
    "venv/",
    "__pycache__/",
    "generated/",
    "coverage/",
    ".git/",
    ".DS_Store",
]


def is_noisy_path(path: str) -> bool:
    """Returns True if a file path belongs to a generated/vendor/noise directory."""
    p = path.replace("\\", "/")
    return any(p.startswith(prefix) or f"/{prefix}" in p for prefix in IGNORED_PATH_PREFIXES)


# ── Entrypoint heuristic ───────────────────────────────────────────────────────
_ENTRYPOINT_NAMES = {
    "main.py", "__main__.py", "app.py", "server.py", "run.py",
    "manage.py", "wsgi.py", "asgi.py", "cli.py",
    "index.js", "index.ts", "main.ts", "main.js", "server.js", "server.ts",
    "app.ts", "app.js",
}


def _is_entrypoint(path: str) -> bool:
    name = PurePosixPath(path).name
    return name in _ENTRYPOINT_NAMES or "/cmd/" in path or "/bin/" in path


class RepoIntelligenceService:
    def __init__(self, db: Session):
        self.db = db

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def get_repo_intelligence(self, repository_id: str) -> RepoIntelligence | None:
        """Load existing RepoIntelligence artifact for a repository."""
        return self.db.scalar(
            select(RepoIntelligence).where(RepoIntelligence.repository_id == repository_id)
        )

    def build_repo_intelligence(self, repository: Repository) -> RepoIntelligence:
        """
        Build and persist a full repo-wide intelligence artifact.

        Steps:
        1. Collect source files (excluding noisy paths)
        2. Score importance and identify structure
        3. Call Gemini to produce structured intelligence
        4. Persist as RepoIntelligence (upsert)
        """
        logger.info(f"[IntelligenceService] Building repo intelligence for {repository.full_name}")

        # ── Step 1: Load all source files, excluding noisy paths ──────────────
        all_files = list(
            self.db.scalars(
                select(File).where(
                    File.repository_id == repository.id,
                    File.content.is_not(None),
                )
            ).all()
        )

        # Filter noisy paths
        source_files = [f for f in all_files if not is_noisy_path(f.path)]
        total_source = len(source_files)

        # ── Step 2: Classify files by role ───────────────────────────────────
        entrypoints = [f.path for f in source_files if _is_entrypoint(f.path)]

        # Backend: Python, Go, Java, Ruby, Rust, etc.
        backend_ext = {".py", ".go", ".java", ".rb", ".rs", ".php", ".cs", ".cpp", ".c"}
        frontend_ext = {".tsx", ".jsx", ".vue", ".svelte", ".html", ".css", ".scss"}
        backend_paths = sorted({
            f.path for f in source_files
            if f.extension in backend_ext
        })[:30]
        frontend_paths = sorted({
            f.path for f in source_files
            if f.extension in frontend_ext
        })[:30]

        top_level_dirs = sorted({
            f.path.split("/")[0] for f in source_files if "/" in f.path
        })

        # ── Step 3: Pick key files for Gemini context ─────────────────────────
        # score: entrypoint + manifest + high-symbol + low-path-depth
        symbol_counts = dict(
            self.db.execute(
                select(Symbol.file_id, Symbol.file_id)
                .where(Symbol.repository_id == repository.id)
            ).all()  # type: ignore
        )
        # Better approach: count symbols per file
        from sqlalchemy import func
        sym_counts: dict[str, int] = dict(
            self.db.execute(
                select(Symbol.file_id, func.count(Symbol.id))
                .where(Symbol.repository_id == repository.id)
                .group_by(Symbol.file_id)
            ).all()
        )

        inbound_counts: dict[str, int] = dict(
            self.db.execute(
                select(DependencyEdge.target_file_id, func.count(DependencyEdge.id))
                .where(DependencyEdge.repository_id == repository.id)
                .group_by(DependencyEdge.target_file_id)
            ).all()
        )

        scored_files = []
        for f in source_files:
            if f.file_kind not in {"source", "config", "build", "script", "test", "doc"}:
                continue
            score = (
                min((f.line_count or 0) / 20.0, 15.0)
                + min(sym_counts.get(f.id, 0) * 2.0, 20.0)
                + min(inbound_counts.get(f.id, 0) * 4.0, 20.0)
                + (20.0 if _is_entrypoint(f.path) else 0.0)
                + (10.0 if "route" in f.path.lower() or "api" in f.path.lower() else 0.0)
                + (8.0  if "model" in f.path.lower() or "schema" in f.path.lower() else 0.0)
                + (8.0  if "config" in f.path.lower() else 0.0)
                + (5.0  if "auth" in f.path.lower() else 0.0)
                + (5.0  if "db" in f.path.lower() or "database" in f.path.lower() else 0.0)
                - float(f.path.count("/")) * 0.5   # penalise deep paths slightly
            )
            scored_files.append((score, f))

        scored_files.sort(key=lambda x: x[0], reverse=True)
        key_files_records = [f for _, f in scored_files[:60]]

        # Also update importance_score on File rows
        for score, f in scored_files[:100]:
            f.importance_score = round(score, 2)
        self.db.flush()

        # ── Step 4: Build context bundle for Gemini ───────────────────────────
        key_files_paths = [f.path for f in key_files_records[:30]]

        context_blocks: list[str] = []

        # Manifests first (README, package.json, requirements.txt, etc.)
        manifests = [
            f for f in source_files
            if any(k in f.path.lower() for k in ["readme", "package.json", "requirements.txt", "pyproject.toml", "cargo.toml", ".env.example"])
        ]
        for m in manifests[:5]:
            snippet = (m.content or "")[:3000]
            context_blocks.append(f"=== MANIFEST: {m.path} ===\n{snippet}")

        # Key source files
        for f in key_files_records[:20]:
            if f in manifests:
                continue
            snippet = (f.content or "")[:2000]
            context_blocks.append(f"=== SOURCE FILE: {f.path} ===\n{snippet}")

        file_list_text = "\n".join(f"- {f.path} ({f.language}, {f.line_count}L)" for f in source_files[:100])

        full_context = "\n\n".join(context_blocks)[:40000]

        # ── Step 5: Call Gemini for structured intelligence ───────────────────
        intel_data: dict = {}
        chat_provider = get_chat_provider()
        if chat_provider:
            system_prompt = (
                "You are a senior software architect analyzing a code repository. "
                "Return a JSON object with EXACTLY these keys (no markdown fences, raw JSON only):\n"
                "frameworks, build_tools, test_frameworks, entrypoints, backend_summary, frontend_summary, "
                "api_routes_summary, db_summary, auth_summary, deployment_summary, "
                "repo_summary_text, architecture_summary_text, module_map_text, detected_services, detected_apps.\n\n"
                "Rules:\n"
                "- frameworks: list of framework names (e.g. [\"FastAPI\", \"Next.js\"])\n"
                "- build_tools: list of tools (e.g. [\"pnpm\", \"Docker\"])\n"
                "- test_frameworks: list (e.g. [\"pytest\"])\n"
                "- entrypoints: list of file paths that are the main entry points\n"
                "- backend_summary: 2-3 sentences describing backend architecture\n"
                "- frontend_summary: 2-3 sentences describing frontend if present, else null\n"
                "- api_routes_summary: list or description of main API routes/endpoints found\n"
                "- db_summary: Describe database models/engines/ORMs found. ONLY if evidence exists. If no DB found, state 'No database detected'.\n"
                "- auth_summary: describe authentication mechanism if found\n"
                "- deployment_summary: describe deployment setup (Docker, CI, etc.) if found\n"
                "- repo_summary_text: 3-4 paragraph executive summary of what this repo does\n"
                "- architecture_summary_text: technical description of the architecture pattern\n"
                "- module_map_text: bullet list of major modules and what they do\n"
                "- detected_services: list of microservices or major logical services\n"
                "- detected_apps: list of distinct apps (e.g. [\"api\", \"web\"])\n"
                "Return ONLY valid JSON. No explanation outside the JSON."
            )
            user_prompt = (
                f"Repository: {repository.full_name}\n"
                f"Languages: {repository.detected_languages or 'unknown'}\n"
                f"Detected frameworks: {repository.detected_frameworks or 'unknown'}\n\n"
                f"FILE INVENTORY (top 100 source files):\n{file_list_text}\n\n"
                f"FILE CONTENTS (key files):\n{full_context}"
            )
            try:
                raw = chat_provider.answer(system_prompt, user_prompt).strip()
                # Strip markdown fences if Gemini adds them
                if raw.startswith("```"):
                    raw = raw.split("```", 2)[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                    raw = raw.rsplit("```", 1)[0]
                intel_data = json.loads(raw)
                logger.info(f"[IntelligenceService] Gemini produced structured intelligence for {repository.full_name}")
            except Exception as e:
                logger.warning(f"[IntelligenceService] Gemini failed, using fallback: {e}")
                intel_data = {}

        # ── Step 6: Upsert RepoIntelligence ──────────────────────────────────
        existing = self.db.scalar(
            select(RepoIntelligence).where(RepoIntelligence.repository_id == repository.id)
        )

        def _jdump(val: object) -> str | None:
            if val is None:
                return None
            if isinstance(val, str):
                return val
            return json.dumps(val)

        def _str_or_none(val: object) -> str | None:
            if val is None:
                return None
            if isinstance(val, list):
                return "\n".join(str(v) for v in val)
            return str(val)

        record_kwargs: dict = {
            "repository_id": repository.id,
            "primary_language": repository.primary_language,
            "frameworks":          _jdump(intel_data.get("frameworks") or (repository.detected_frameworks or "").split(",") if repository.detected_frameworks else None),
            "build_tools":          _jdump(intel_data.get("build_tools")),
            "test_frameworks":      _jdump(intel_data.get("test_frameworks")),
            "top_level_dirs":       _jdump(top_level_dirs),
            "entrypoints":          _jdump(intel_data.get("entrypoints") or entrypoints),
            "key_files":            _jdump(key_files_paths),
            "detected_services":    _jdump(intel_data.get("detected_services")),
            "detected_apps":        _jdump(intel_data.get("detected_apps")),
            "backend_paths":        _jdump(backend_paths[:20]),
            "frontend_paths":       _jdump(frontend_paths[:20]),
            "api_routes_summary":   _str_or_none(intel_data.get("api_routes_summary")),
            "db_summary":           _str_or_none(intel_data.get("db_summary")),
            "auth_summary":         _str_or_none(intel_data.get("auth_summary")),
            "deployment_summary":   _str_or_none(intel_data.get("deployment_summary")),
            "repo_summary_text":    _str_or_none(intel_data.get("repo_summary_text")),
            "architecture_summary_text": _str_or_none(intel_data.get("architecture_summary_text")),
            "module_map_text":      _str_or_none(intel_data.get("module_map_text")),
            "total_source_files":   total_source,
            "total_symbols":        sum(sym_counts.values()),
        }

        if existing:
            for k, v in record_kwargs.items():
                if k != "repository_id":
                    setattr(existing, k, v)
            existing.ingestion_version = (existing.ingestion_version or 0) + 1
            self.db.commit()
            self.db.refresh(existing)
            logger.info(f"[IntelligenceService] Updated RepoIntelligence v{existing.ingestion_version} for {repository.full_name}")
            return existing
        else:
            new_intel = RepoIntelligence(**record_kwargs)
            self.db.add(new_intel)
            self.db.commit()
            self.db.refresh(new_intel)
            logger.info(f"[IntelligenceService] Created RepoIntelligence for {repository.full_name}")
            return new_intel

    def build_file_summaries(self, repository: Repository, max_files: int = 50) -> dict:
        """
        Generate LLM summaries for the top-N most important source files.
        Updates File.summary_text, File.responsibilities, File.imports_list, File.exports_list.
        """
        chat_provider = get_chat_provider()
        if not chat_provider:
            return {"status": "skipped", "reason": "No LLM provider"}

        # Get top files by importance score
        top_files = list(
            self.db.scalars(
                select(File).where(
                    File.repository_id == repository.id,
                    File.importance_score.is_not(None),
                    File.content.is_not(None),
                    File.file_kind == "source",
                ).order_by(File.importance_score.desc()).limit(max_files)
            ).all()
        )

        enriched = 0
        for f in top_files:
            if not f.content:
                continue
            try:
                system_prompt = (
                    "You are a code understanding assistant. Analyze the given source file and return "
                    "a JSON object with EXACTLY these keys (raw JSON, no markdown fences):\n"
                    "summary_text, responsibilities, imports_list, exports_list, framework_hints.\n"
                    "- summary_text: 2-3 sentence description of what this file does\n"
                    "- responsibilities: JSON array of 3-5 bullet points (strings)\n"
                    "- imports_list: JSON array of the main modules/packages imported\n"
                    "- exports_list: JSON array of the main symbols exported or defined\n"
                    "- framework_hints: JSON array of framework names detected (e.g. ['FastAPI', 'SQLAlchemy'])\n"
                    "Return ONLY valid JSON."
                )
                user_prompt = f"FILE: {f.path}\n\n{(f.content or '')[:4000]}"
                raw = chat_provider.answer(system_prompt, user_prompt).strip()
                if raw.startswith("```"):
                    raw = raw.split("```", 2)[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                    raw = raw.rsplit("```", 1)[0]
                data = json.loads(raw)
                f.summary_text = data.get("summary_text")
                f.responsibilities = json.dumps(data.get("responsibilities") or [])
                f.imports_list = json.dumps(data.get("imports_list") or [])
                f.exports_list = json.dumps(data.get("exports_list") or [])
                f.framework_hints = json.dumps(data.get("framework_hints") or [])
                enriched += 1
            except Exception as e:
                logger.warning(f"[IntelligenceService] File summary failed for {f.path}: {e}")

        self.db.commit()
        logger.info(f"[IntelligenceService] Enriched {enriched}/{len(top_files)} file summaries")
        return {"status": "completed", "enriched": enriched, "attempted": len(top_files)}
