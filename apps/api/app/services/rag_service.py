"""RAG (Retrieval-Augmented Generation) service for Ask Repo.

Robust fallback chain:
  A. Semantic search (vector embeddings)    -- used if embeddings exist
  B. Hybrid search (keyword + file content) -- used when embeddings are missing
  C. File-level keyword search              -- last resort before no_context
  D. no_context                             -- only if repository has zero indexed content
"""
from __future__ import annotations

import logging

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.embedding_chunk import EmbeddingChunk
from app.db.models.file import File
from app.db.models.symbol import Symbol
from app.llm.prompt_builder import build_system_prompt, build_user_prompt
from app.llm.providers import get_chat_provider
from app.services.embedding_service import EmbeddingService
from app.services.graph_service import GraphService
import re

logger = logging.getLogger(__name__)

class QueryIntent:
    REPO_SUMMARY = "repo_summary"
    FILE_LOOKUP = "file_lookup"
    SYMBOL_LOOKUP = "symbol_lookup"
    DEPENDENCY_TRACE = "dependency_trace"
    LINE_IMPACT = "line_impact"
    LINE_CHANGE_IMPACT = "line_change_impact"
    FILE_IMPACT = "file_impact"
    CODE_SNIPPET_IMPACT = "code_snippet_impact"
    SEMANTIC_QA = "semantic_qa"


class QueryClassifier:
    @staticmethod
    def classify(question: str) -> dict:
        q = question.lower()
        raw = question  # preserve original casing for snippet extraction

        # ---- PRIORITY -1: Repo-wide summary / overview questions — catch FIRST
        # These must never fall through to generic semantic fallback.
        _REPO_SUMMARY_PHRASES = [
            "what does this repo do", "what does this project do",
            "what does the repo do", "what does the project do",
            "summarize this repo", "summarize this project",
            "summarize the repo", "summarize the project",
            "explain this repo", "explain this project",
            "explain the repo", "explain the project",
            "what is this repo", "what is this project",
            "what is this codebase", "what is this code",
            "what is this app", "what is this application",
            "overview of this repo", "overview of the repo",
            "overview of this project", "give me an overview",
            "how does this repo work", "how does the repo work",
            "how does this project work", "how does the project work",
            "what is this for", "what is this used for",
            "what does this do", "what is this",
            "describe this repo", "describe this project",
            "describe the codebase", "tell me about this repo",
            "tell me about this project", "what is the purpose",
            "project summary", "repo summary", "codebase overview",
        ]
        if any(phrase in q for phrase in _REPO_SUMMARY_PHRASES):
            return {"intent": QueryIntent.REPO_SUMMARY}

        # Catches: "rename heading to h", "change heading to h",
        # "what'll happen if I change JLabel heading = ... heading to h"
        # Pattern: look for "X to Y" where X and Y are identifiers, and a change/rename verb nearby
        _RENAME_PAT = re.compile(
            r"(?:rename|change|renames?)\s+"
            r"(?:[^\n]*?)?"           # optional pasted code in between
            r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b"   # symbol name (old)
            r"\s+to\s+"
            r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b",  # new name
            re.IGNORECASE | re.DOTALL,
        )
        rename_match = _RENAME_PAT.search(raw)
        if rename_match:
            symbol_name = rename_match.group(1).strip()
            new_name = rename_match.group(2).strip()
            # Skip if this looks like a file-path rename (has dots/slashes)
            if "." not in symbol_name and "/" not in symbol_name:
                # Extract the pasted code snippet if present (text before the "X to Y" at the end)
                # Look for multiline content suggesting a pasted declaration
                lines_in_query = raw.strip().splitlines()
                code_snippet = None
                for line in lines_in_query:
                    l = line.strip()
                    # A line that looks like actual code (has = or (); or starts with a type keyword)
                    if ("=" in l or l.endswith(";") or l.endswith("{") or
                            any(k in l for k in ["new ", "JLabel", "JPanel", "import ", "public ", "private "])):
                        code_snippet = l
                        break  # take first code-looking line as the declaration to resolve
                return {
                    "intent": QueryIntent.LINE_CHANGE_IMPACT,
                    "operation": "rename",
                    "symbol_name": symbol_name,
                    "new_name": new_name,
                    "old_text": code_snippet or symbol_name,  # used by LineResolver
                    "new_text": new_name,
                    "file": "",
                }

        # ---- PRIORITY 1: line N in file + change/replace question
        # e.g. "replace X with Y in app/main.py" or "change line 5 in ..."
        change_file_line = re.search(
            r"(?:replace|change|modify)\s+(?:line\s+(\d+)\s+in\s+)?([a-zA-Z0-9\/\._\-]+)",
            q,
        )
        # replace `X` with `Y` in file  (backtick/quote conflict avoided via compiled pattern)
        _REPLACE_PAT = re.compile(
            r"replace\s+[`'\"\u2018\u2019]?(.+?)[`'\"\u2018\u2019]?"
            r"\s+with\s+[`'\"\u2018\u2019]?(.+?)[`'\"\u2018\u2019]?"
            r"(?:\s+in\s+([a-zA-Z0-9/._\-]+))?",
            re.IGNORECASE,
        )
        replace_match = _REPLACE_PAT.search(raw)
        if replace_match:
            return {
                "intent": QueryIntent.LINE_CHANGE_IMPACT,
                "old_text": replace_match.group(1).strip(),
                "new_text": replace_match.group(2).strip(),
                "file": replace_match.group(3) or "",
            }

        # ---- PRIORITY 2: explicit line number + file path (delete/change)
        line_num_match = re.search(
            r"(?:delete|remove|change|modify)?\s*line\s+(\d+)\s+in\s+([a-zA-Z0-9\/\._\-]+)",
            q,
        )
        if line_num_match:
            return {
                "intent": QueryIntent.LINE_IMPACT,
                "line": int(line_num_match.group(1)),
                "file": line_num_match.group(2),
                "snippet": None,
                "operation": "delete" if any(x in q for x in ["delete", "remove"]) else "change",
            }

        # ---- PRIORITY 3: backtick/quoted snippet in a file path (delete `snippet` in file)
        snippet_in_file = re.search(
            r"(?:delete|remove|change)\s+[`'\"](.+?)[`'\"]\s+(?:from\s+|in\s+)([a-zA-Z0-9\/\._\-]+)",
            raw,
            re.IGNORECASE,
        )
        if snippet_in_file:
            return {
                "intent": QueryIntent.LINE_IMPACT,
                "snippet": snippet_in_file.group(1).strip(),
                "file": snippet_in_file.group(2).strip(),
                "line": None,
                "operation": "delete" if "delete" in q else "change",
            }

        # ---- PRIORITY 4: "delete/remove this line" with pasted code (no file)
        if any(m in q for m in ["delete this line", "remove this line", "change this line"]):
            snippet = re.sub(
                r"what\s+(?:will\s+)?(?:happen|happens|breaks)\s+if\s+i\s+(?:delete|remove|change)\s+this\s+line\??",
                "",
                raw,
                flags=re.IGNORECASE,
            ).strip(" ?'\"\n")
            return {
                "intent": QueryIntent.CODE_SNIPPET_IMPACT,
                "snippet": snippet,
                "file": "",
            }

        # ---- PRIORITY 5: "what happens if I delete <code-like string> in file"
        # Catch: "what happens if I delete `from app.routes import auth` in ..."
        # delete/remove <snippet> in <file> (backtick/quote conflict avoided via compiled pattern)
        _LOOSE_SNIPPET_PAT = re.compile(
            r"(?:delete|remove)\s+[`'\"\u2018\u2019]?([a-zA-Z_].+?)[`'\"\u2018\u2019]?"
            r"\s+in\s+([a-zA-Z0-9/._\-]+)",
            re.IGNORECASE,
        )
        loose_snippet_in_file = _LOOSE_SNIPPET_PAT.search(raw)
        if loose_snippet_in_file:
            return {
                "intent": QueryIntent.LINE_IMPACT,
                "snippet": loose_snippet_in_file.group(1).strip(),
                "file": loose_snippet_in_file.group(2).strip(),
                "line": None,
                "operation": "delete",
            }

        # ---- PRIORITY 6: File impact stub
        file_impact_match = re.search(
            r"(?:delete|remove|change)\s+([a-zA-Z0-9\/\._\-]+\.[a-zA-Z0-9]+)", q
        )
        if file_impact_match:
            return {
                "intent": QueryIntent.FILE_IMPACT,
                "file": file_impact_match.group(1),
            }

        # ---- PRIORITY 7: Repo Summary (kept as fallback for edge phrases)
        # Main detection is PRIORITY -1 at the top of classify()
        if any(x in q for x in ["how does it work", "overview", "this project", "this repo"]):
            return {"intent": QueryIntent.REPO_SUMMARY}

        # ---- PRIORITY 8: Dependency Trace
        if any(x in q for x in ["depend on", "depends on", "imports", "who calls", "references", "handle deployment", "deploy"]):
            dep_match = re.search(r"(?:depend on|depends on|imports|who calls|references)\s+([a-zA-Z0-9\/\._\-]+)", q)
            target = dep_match.group(1) if dep_match else "deployment"
            return {"intent": QueryIntent.DEPENDENCY_TRACE, "target": target}

        # ---- PRIORITY 9: Symbol Lookup
        if any(x in q for x in ["where is", "where are", "where do we", "entrypoint", "implemented"]):
            return {"intent": QueryIntent.SYMBOL_LOOKUP}

        # ---- PRIORITY 10: File Lookup
        if any(x in q for x in ["find ", "show me file", "file "]):
            return {"intent": QueryIntent.FILE_LOOKUP}

        # Default
        return {"intent": QueryIntent.SEMANTIC_QA}


# ---------------------------------------------------------------------------
# Line Type Detector — classifies what a single code line does
# ---------------------------------------------------------------------------

class LineTypeDetector:
    # Ordered patterns — first match wins
    _PATTERNS = [
        ("import",          re.compile(r"^\s*(import |from .+ import )", re.IGNORECASE)),
        ("router_include",  re.compile(r"include_router", re.IGNORECASE)),
        ("middleware_reg",  re.compile(r"add_middleware", re.IGNORECASE)),
        ("db_init",         re.compile(r"(create_engine|sessionmaker|Base\.metadata\.create_all)", re.IGNORECASE)),
        ("decorator",       re.compile(r"^\s*@")),
        ("function_def",    re.compile(r"^\s*(async\s+)?def \w+")),
        ("class_def",       re.compile(r"^\s*class \w+")),
        ("route_def",       re.compile(r"@(app|router)\.(get|post|put|delete|patch|options|head)\(", re.IGNORECASE)),
        ("return_stmt",     re.compile(r"^\s*return ")),
        ("assignment",      re.compile(r"^\s*\w+\s*=")),
        ("function_call",   re.compile(r"^\s*[a-zA-Z_][\w.]*\s*\(")),
        ("env_lookup",      re.compile(r"(os\.environ|os\.getenv|config\.get|settings\.)", re.IGNORECASE)),
        ("exception",       re.compile(r"^\s*(try:|except |raise |finally:)")),
    ]

    @classmethod
    def detect(cls, line_text: str) -> str:
        for name, pat in cls._PATTERNS:
            if pat.search(line_text):
                return name
        return "other"


# ---------------------------------------------------------------------------
# Line Resolver — resolves file path + line number / snippet to exact context
# ---------------------------------------------------------------------------

class LineResolver:
    def __init__(self, db: Session):
        self.db = db

    def resolve(
        self,
        repository_id: str,
        file_hint: str = "",
        line_no: int | None = None,
        snippet: str | None = None,
        context_radius: int = 8,
    ) -> dict | None:
        """
        Returns a resolution dict or None if nothing found.
        Fields: file_path, file_id, line_no, line_text,
                context_before, context_after, enclosing_symbol, line_type, found
        """
        file_record = None

        if file_hint:
            # Try exact path first, then ilike
            file_record = self.db.scalar(
                select(File).where(
                    File.repository_id == repository_id,
                    File.path.ilike(f"%{file_hint}%"),
                )
            )

        resolved_line_no: int | None = line_no

        if file_record and snippet and resolved_line_no is None:
            # Resolve snippet to exact line within this file
            resolved_line_no = self._find_snippet_line(file_record.content or "", snippet)

        elif not file_record and snippet:
            # Global search: find the snippet across all files
            candidates = list(self.db.scalars(
                select(File).where(
                    File.repository_id == repository_id,
                    File.content.ilike(f"%{snippet[:120]}%"),
                ).limit(3)
            ).all())
            if candidates:
                file_record = candidates[0]
                resolved_line_no = self._find_snippet_line(file_record.content or "", snippet)

        if file_record is None or resolved_line_no is None:
            return {
                "found": False,
                "file_hint": file_hint,
                "snippet_searched": snippet or "",
            }

        content = file_record.content or ""
        lines = content.splitlines()
        idx = resolved_line_no - 1  # 0-indexed
        line_text = lines[idx] if 0 <= idx < len(lines) else ""

        before_start = max(0, idx - context_radius)
        after_end = min(len(lines), idx + context_radius + 1)

        context_before = "\n".join(
            f"{before_start + i + 1}: {l}" for i, l in enumerate(lines[before_start:idx])
        )
        context_after = "\n".join(
            f"{idx + i + 2}: {l}" for i, l in enumerate(lines[idx + 1:after_end])
        )

        # Enclosing symbol lookup
        symbol = self.db.scalars(
            select(Symbol).where(
                Symbol.file_id == file_record.id,
                Symbol.start_line <= resolved_line_no,
                Symbol.end_line >= resolved_line_no,
            )
        ).first()
        enclosing = f"{symbol.name} ({symbol.symbol_type})" if symbol else "module-level"

        line_type = LineTypeDetector.detect(line_text)

        return {
            "found": True,
            "file_id": str(file_record.id),
            "file_path": file_record.path,
            "file_record": file_record,
            "line_no": resolved_line_no,
            "line_text": line_text,
            "context_before": context_before,
            "context_after": context_after,
            "enclosing_symbol": enclosing,
            "line_type": line_type,
            "symbol_record": symbol,
        }

    @staticmethod
    def _find_snippet_line(content: str, snippet: str) -> int | None:
        """Returns 1-indexed line number of the first matching line."""
        needle = snippet.strip()
        for i, line in enumerate(content.splitlines()):
            if needle.lower() in line.lower():
                return i + 1
        return None


class RAGService:
    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = EmbeddingService(db)
        self.graph_service = GraphService(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask_repo(self, repository_id: str, question: str, top_k: int = 8) -> dict:
        """
        Retrieves relevant context and answers via LLM or deterministic fallback.
        Enhanced with Query Classification for repository-aware reasoning.
        """
        from app.db.models.repository import Repository
        repo = self.db.get(Repository, repository_id)

        # Stage 0: Classify Intent
        classification = QueryClassifier.classify(question)
        intent = classification["intent"]
        logger.info(f"Classified query intent: {intent}")

        retrieved = []
        notes = []
        line_metadata: dict = {}  # carries resolved line data through to response

        # Stage 1: Specialized Retrieval based on intent
        if intent == QueryIntent.REPO_SUMMARY:
            retrieved = self._retrieve_project_summary(repo)
            notes.append("Using project-level summaries and entrypoints.")

        elif intent in (QueryIntent.LINE_IMPACT, QueryIntent.LINE_CHANGE_IMPACT):
            retrieved, line_metadata = self._retrieve_line_impact_v2(
                repository_id, classification, question
            )
            if line_metadata.get("found"):
                notes.append(
                    f"Resolved {classification.get('file','?')} "
                    f"line {line_metadata.get('line_no','?')}: "
                    f"{line_metadata.get('line_type','?')} statement"
                )
            else:
                notes.append("Line/snippet not found in repository. General explanation provided.")

        elif intent == QueryIntent.CODE_SNIPPET_IMPACT:
            snippet = classification.get("snippet", "")
            if snippet:
                retrieved = self._retrieve_code_snippet(repository_id, snippet)
                if retrieved:
                    notes.append(f"Found exact match for code snippet in {retrieved[0].get('file_path')}.")
                else:
                    notes.append("Code snippet not found in standard repository files.")

        elif intent == QueryIntent.FILE_IMPACT:
            retrieved = self._retrieve_file_impact(repository_id, classification["file"])
            notes.append(f"Analyzing impact for file {classification['file']}")

        elif intent == QueryIntent.DEPENDENCY_TRACE:
            target = classification.get("target")
            if target:
                retrieved = self._retrieve_dependency_trace(repository_id, target)
                notes.append(f"Tracing dependencies for {target}")

        elif intent == QueryIntent.SYMBOL_LOOKUP:
            notes.append("Symbol lookup intent detected, using hybrid semantic search.")

        elif intent == QueryIntent.FILE_LOOKUP:
            notes.append("File lookup intent detected, using hybrid semantic search.")

        # Stage 2: Hybrid Search fallback (skip for snippet/line intents to avoid noise)
        _skip_hybrid = intent in (
            QueryIntent.CODE_SNIPPET_IMPACT,
            QueryIntent.LINE_IMPACT,
            QueryIntent.LINE_CHANGE_IMPACT,
        )
        if not retrieved and not _skip_hybrid:
            try:
                hybrid_results = self.embedding_service.hybrid_search(
                    repository_id=repository_id,
                    query=question,
                    top_k=top_k,
                )
                retrieved.extend(hybrid_results)
            except Exception as e:
                logger.warning(f"hybrid_search failed: {e}")

        # Stage 3: Keyword fallback (also skipped for snippet/line)
        if not retrieved and not _skip_hybrid:
            try:
                retrieved = self._keyword_file_search(repository_id, question, top_k=top_k)
            except Exception as e:
                logger.warning(f"keyword_file_search failed: {e}")

        # Stage 4: Nothing found guard
        snippet_found = bool(retrieved and intent == QueryIntent.CODE_SNIPPET_IMPACT)
        _line_not_found = intent in (QueryIntent.LINE_IMPACT, QueryIntent.LINE_CHANGE_IMPACT) and not line_metadata.get("found")

        if not retrieved and intent not in (
            QueryIntent.CODE_SNIPPET_IMPACT,
            QueryIntent.LINE_IMPACT,
            QueryIntent.LINE_CHANGE_IMPACT,
        ):
            return {
                "answer": "No indexed content found. Please Parse/Embed first.",
                "citations": [],
                "mode": "no_context",
                "llm_model": None,
                "confidence": "low",
                "notes": ["Zero evidence found."],
                "query_type": intent,
                "answer_mode": "no_context",
                "snippet_found": False,
                **self._line_meta_fields(line_metadata),
            }

        # Stage 5: Synthesis
        chat_provider = get_chat_provider()

        if chat_provider is None:
            answer, confidence, det_notes = self._deterministic_answer(question, retrieved, intent)
            return {
                "answer": answer,
                "citations": self._build_citations(retrieved),
                "mode": "deterministic_retrieval",
                "llm_model": None,
                "confidence": confidence,
                "notes": notes + det_notes,
                "query_type": intent,
                "answer_mode": "deterministic_fallback",
                "snippet_found": snippet_found,
                **self._line_meta_fields(line_metadata),
            }

        system_prompt = build_system_prompt()
        # Route to specialized prompts based on intent
        if intent in (QueryIntent.LINE_IMPACT, QueryIntent.LINE_CHANGE_IMPACT) and line_metadata:
            from app.llm.prompt_builder import build_line_impact_prompt
            user_prompt = build_line_impact_prompt(question, retrieved, line_metadata, intent)
        elif intent == QueryIntent.REPO_SUMMARY:
            from app.llm.prompt_builder import build_repo_summary_prompt
            user_prompt = build_repo_summary_prompt(question, retrieved)
        else:
            user_prompt = build_user_prompt(question, retrieved, intent=intent)

        logger.info(f"[ASK_REPO] Gemini request STARTED — model={chat_provider.model_name!r}, intent={intent!r}, evidence_chunks={len(retrieved)}")
        try:
            answer = chat_provider.answer(system_prompt, user_prompt).strip()
            answer = self._sanitize_answer(answer)
            logger.info(f"[ASK_REPO] Gemini response SUCCEEDED — answer_length={len(answer)}")
            return {
                "answer": answer,
                "citations": self._build_citations(retrieved),
                "mode": "gemini_synthesized",
                "llm_model": chat_provider.model_name,
                "confidence": "high" if line_metadata.get("found") else ("high" if len(retrieved) >= 3 else "medium"),
                "notes": notes,
                "query_type": intent,
                "answer_mode": "gemini_synthesized",
                "snippet_found": snippet_found,
                **self._line_meta_fields(line_metadata),
            }
        except Exception as e:
            logger.error(f"[ASK_REPO] Gemini FAILED — reason: {e!r}. Falling back to deterministic.")
            answer, confidence, det_notes = self._deterministic_answer(question, retrieved, intent, line_metadata)
            answer = self._sanitize_answer(answer)
            return {
                "answer": answer,
                "citations": self._build_citations(retrieved),
                "mode": "gemini_failed_fallback",
                "llm_model": None,
                "confidence": confidence,
                "notes": notes + det_notes + [f"Gemini failed: {type(e).__name__}"],
                "query_type": intent,
                "answer_mode": "gemini_failed_fallback",
                "snippet_found": snippet_found,
                **self._line_meta_fields(line_metadata),
            }

    @staticmethod
    def _line_meta_fields(line_metadata: dict) -> dict:
        """Extracts safe, serializable fields from line_metadata for the response."""
        if not line_metadata:
            return {}
        return {
            "resolved_file": line_metadata.get("file_path"),
            "resolved_line_number": line_metadata.get("line_no"),
            "matched_line": line_metadata.get("line_text"),
            "enclosing_scope": line_metadata.get("enclosing_symbol"),
            "line_type": line_metadata.get("line_type"),
            "snippet_found": line_metadata.get("found", False),
            "rename_analysis": line_metadata.get("rename_analysis"),
        }

    @staticmethod
    def _sanitize_answer(text: str) -> str:
        """
        Strips raw markdown artifacts from any LLM response so the UI
        never shows ###, **, *, backticks, or fenced code blocks.
        """
        import re as _re
        # Remove fenced code block delimiters (```lang ... ```)
        text = _re.sub(r"```[a-zA-Z]*\n?", "", text)
        text = _re.sub(r"```", "", text)
        # Remove markdown headings (###, ##, #) at start of line — keep text
        text = _re.sub(r"^#{1,6}\s+", "", text, flags=_re.MULTILINE)
        # Strip bold/italic: **text**, __text__, *text*, _text_
        text = _re.sub(r"\*{2}(.+?)\*{2}", r"\1", text, flags=_re.DOTALL)
        text = _re.sub(r"_{2}(.+?)_{2}", r"\1", text, flags=_re.DOTALL)
        text = _re.sub(r"\*(.+?)\*", r"\1", text, flags=_re.DOTALL)
        text = _re.sub(r"_([^_\s][^_]*[^_\s]?)_", r"\1", text)
        # Strip inline backticks
        text = _re.sub(r"`([^`]+)`", r"\1", text)
        # Collapse triple+ blank lines
        text = _re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


    def _retrieve_project_summary(self, repository) -> list[dict]:
        """
        Generalized, hierarchy-enforced repo-intelligence evidence gathering.
        Priority: Stored Metadata > README/Docs > Manifests > Entrypoints.
        """
        _NOISE_PATTERNS = [
            ".gitignore", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
            "node_modules", "dist/", ".next/", "build/", "coverage/", "vendor/",
            "__pycache__", ".pyc", ".min.js", ".map", ".lock",
        ]

        def _is_noisy(path: str) -> bool:
            p = path.lower()
            return any(n in p for n in _NOISE_PATTERNS)

        results: list[dict] = []

        # ── Tier 1: Stored repository metadata
        meta_parts = []
        if repository.summary:
            meta_parts.append(f"Summary: {repository.summary}")
        if getattr(repository, "primary_language", None):
            meta_parts.append(f"Language: {repository.primary_language}")
        if getattr(repository, "framework", None):
            meta_parts.append(f"Framework: {repository.framework}")
            
        if meta_parts:
            results.append({
                "file_path": "REPO_METADATA",
                "snippet": "REPOSITORY ATTRIBUTES:\n" + "\n".join(meta_parts),
                "score": 1.0,
                "match_type": "repo_metadata",
            })

        # ── Tier 2: README and documentation (Top 5)
        readme_files = list(self.db.scalars(
            select(File).where(
                File.repository_id == repository.id,
                or_(
                    File.path.ilike("README%"),
                    File.path.ilike("%/README%"),
                    File.path.ilike("docs/index%"),
                    File.path.ilike("docs/README%"),
                )
            ).limit(5)
        ).all())
        for f in readme_files:
            if not _is_noisy(f.path):
                results.append({
                    "file_id": str(f.id),
                    "file_path": f.path,
                    "snippet": f"README CONTENT ({f.path}):\n{(f.content or '')[:3000]}",
                    "score": 0.98,
                    "match_type": "readme",
                })

        # ── Tier 3: Primary Manifests (Dependency Evidence)
        manifest_files = list(self.db.scalars(
            select(File).where(
                File.repository_id == repository.id,
                or_(
                    File.path == "package.json",
                    File.path == "requirements.txt",
                    File.path == "pyproject.toml",
                    File.path == "go.mod",
                    File.path == "pom.xml",
                    File.path == "build.gradle",
                    File.path == "Cargo.toml",
                    File.path == "Pipfile",
                )
            ).limit(8)
        ).all())
        for f in manifest_files:
            results.append({
                "file_id": str(f.id),
                "file_path": f.path,
                "snippet": f"PROJECT MANIFEST ({f.path}):\n{(f.content or '')[:2000]}",
                "score": 0.95,
                "match_type": "manifest",
            })

        # ── Tier 4: App Entrypoints / Bootstrap files
        entrypoint_files = list(self.db.scalars(
            select(File).where(
                File.repository_id == repository.id,
                or_(
                    File.path.ilike("main.py"),
                    File.path.ilike("app.py"),
                    File.path.ilike("index.js"),
                    File.path.ilike("server.js"),
                    File.path.ilike("manage.py"),
                    File.path.ilike("App.tsx"),
                    File.path.ilike("main.tsx"),
                    File.path.ilike("next.config.js"),
                )
            ).limit(10)
        ).all())
        for f in entrypoint_files:
            if not _is_noisy(f.path):
                results.append({
                    "file_id": str(f.id),
                    "file_path": f.path,
                    "snippet": f"ENTRYPOINT CODE ({f.path}):\n{(f.content or '')[:1500]}",
                    "score": 0.92,
                    "match_type": "entrypoint",
                })

        return results

        return results


    def _retrieve_code_snippet(self, repository_id: str, snippet: str) -> list[dict]:
        """Looks for an exact substring match of the snippet in all files."""
        from sqlalchemy import select
        
        # We need an exact substring match logic. SQLite/Postgres `ilike` with wildcards works.
        term = snippet.strip()
        if not term:
            return []
            
        # Limit to reasonable length
        if len(term) > 200:
            term = term[:200]
            
        files = self.db.scalars(
            select(File).where(
                File.repository_id == repository_id,
                File.content.ilike(f"%{term}%")
            ).limit(3)
        ).all()
        
        results = []
        for file in files:
            # Find exact line number to provide context
            content = file.content or ""
            lines = content.splitlines()
            line_no = 1
            for i, line in enumerate(lines):
                if term.lower() in line.lower():
                    line_no = i + 1
                    break
                    
            start_line = max(1, line_no - 5)
            end_line = line_no + 5
            context = "\n".join(lines[start_line - 1:end_line])
            
            results.append({
                "file_id": str(file.id),
                "file_path": file.path,
                "start_line": start_line,
                "end_line": end_line,
                "snippet": f"Found matching snippet at line {line_no}:\n{context}",
                "match_type": "snippet_match",
                "score": 1.0,
            })
            
            # Use self._retrieve_line_impact conditionally to fetch dependents if possible
            # Just fetch the symbol
            symbol = self.db.scalars(
                select(Symbol).where(
                    Symbol.file_id == file.id,
                    Symbol.start_line <= line_no,
                    Symbol.end_line >= line_no
                )
            ).first()
            
            if symbol:
                results.append({
                    "file_id": None,
                    "file_path": file.path,
                    "snippet": f"Snippet is inside symbol: {symbol.name}. Summary: {symbol.summary or 'N/A'}",
                    "match_type": "impact_symbol",
                    "score": 0.95,
                })
        
        return results

    def _retrieve_line_impact_v2(
        self,
        repository_id: str,
        classification: dict,
        question: str,
    ) -> tuple[list[dict], dict]:
        """
        Full true line-level impact retrieval.
        Returns (evidence_list, line_metadata_dict).
        """
        resolver = LineResolver(self.db)
        # For LINE_CHANGE_IMPACT, use old_text as snippet if no explicit snippet given
        effective_snippet = classification.get("snippet") or classification.get("old_text") or None
        res = resolver.resolve(
            repository_id=repository_id,
            file_hint=classification.get("file", ""),
            line_no=classification.get("line"),
            snippet=effective_snippet,
        )

        if not res or not res.get("found"):
            # --- Rename fallback: even if full snippet not found, try finding the symbol by name ---
            symbol_name = classification.get("symbol_name")
            if symbol_name and classification.get("operation") == "rename":
                # Try to find any file containing the symbol
                candidates = list(self.db.scalars(
                    select(File).where(
                        File.repository_id == repository_id,
                        File.content.ilike(f"% {symbol_name} %"),
                    ).limit(3)
                ).all())
                # Try via Symbol table too
                sym_candidates = list(self.db.scalars(
                    select(Symbol).where(
                        Symbol.repository_id == repository_id,
                        Symbol.name == symbol_name,
                    ).limit(3)
                ).all())
                if sym_candidates:
                    # Prefer symbol table result
                    sym = sym_candidates[0]
                    file_rec = self.db.get(File, sym.file_id)
                    if file_rec:
                        refs = self._scan_same_file_references(
                            file_rec.content or "", symbol_name, sym.start_line
                        )
                        lang = self._infer_language(file_rec.path)
                        rename_analysis = {
                            "symbol_name": symbol_name,
                            "new_name": classification.get("new_name", classification.get("new_text", "")),
                            "declaration_line": sym.start_line,
                            "same_file_references": refs,
                            "declaration_only_rename_breaks": len(refs) > 0,
                            "full_rename_safe": True,
                            "language": lang,
                            "error_if_partial": (
                                f"error: cannot find symbol: {symbol_name}"
                                if lang == "java" else
                                f"NameError: name '{symbol_name}' is not defined"
                            ),
                        }
                        meta = {
                            "found": True,
                            "file_path": file_rec.path,
                            "line_no": sym.start_line,
                            "line_text": (file_rec.content or "").splitlines()[sym.start_line - 1]
                                if sym.start_line <= len((file_rec.content or "").splitlines()) else "",
                            "line_type": "assignment",
                            "enclosing_symbol": f"{sym.name} ({sym.symbol_type})",
                            "rename_analysis": rename_analysis,
                        }
                        ev = [{
                            "file_id": str(file_rec.id),
                            "file_path": file_rec.path,
                            "start_line": max(1, sym.start_line - 5),
                            "end_line": sym.start_line + 5,
                            "snippet": (
                                f"FILE: {file_rec.path}\n"
                                f"SYMBOL '{symbol_name}' declared at line {sym.start_line} "
                                f"(type={sym.symbol_type})\n"
                                f"SAME-FILE REFERENCES AFTER DECLARATION ({len(refs)}):\n"
                                + "\n".join(f"  line {r['line_no']}: {r['line_text']}" for r in refs)
                            ),
                            "match_type": "rename_analysis",
                            "score": 1.0,
                        }]
                        return ev, meta
                elif candidates:
                    file_rec = candidates[0]
                    # Find the declaration line for symbol_name
                    decl_line = LineResolver._find_snippet_line(
                        file_rec.content or "", symbol_name
                    )
                    if decl_line:
                        refs = self._scan_same_file_references(
                            file_rec.content or "", symbol_name, decl_line
                        )
                        lang = self._infer_language(file_rec.path)
                        rename_analysis = {
                            "symbol_name": symbol_name,
                            "new_name": classification.get("new_name", classification.get("new_text", "")),
                            "declaration_line": decl_line,
                            "same_file_references": refs,
                            "declaration_only_rename_breaks": len(refs) > 0,
                            "full_rename_safe": True,
                            "language": lang,
                            "error_if_partial": (
                                f"error: cannot find symbol: {symbol_name}"
                                if lang == "java" else
                                f"NameError: name '{symbol_name}' is not defined"
                            ),
                        }
                        decl_text = (file_rec.content or "").splitlines()[decl_line - 1] \
                            if decl_line <= len((file_rec.content or "").splitlines()) else ""
                        meta = {
                            "found": True,
                            "file_path": file_rec.path,
                            "line_no": decl_line,
                            "line_text": decl_text,
                            "line_type": "assignment",
                            "enclosing_symbol": "unknown",
                            "rename_analysis": rename_analysis,
                        }
                        ev = [{
                            "file_id": str(file_rec.id),
                            "file_path": file_rec.path,
                            "start_line": max(1, decl_line - 5),
                            "end_line": decl_line + 5,
                            "snippet": (
                                f"FILE: {file_rec.path}\n"
                                f"DECLARATION of '{symbol_name}' found at line {decl_line}: {decl_text}\n"
                                f"SAME-FILE REFERENCES AFTER DECLARATION ({len(refs)}):\n"
                                + "\n".join(f"  line {r['line_no']}: {r['line_text']}" for r in refs)
                            ),
                            "match_type": "rename_analysis",
                            "score": 1.0,
                        }]
                        return ev, meta

            # No resolution at all — return empty evidence
            return [], {"found": False, "file_hint": classification.get("file", "")}

        file_record = res["file_record"]
        line_no = res["line_no"]
        line_text = res["line_text"]
        line_type = res["line_type"]
        enclosing = res["enclosing_symbol"]
        symbol = res.get("symbol_record")

        # ── Rename analysis (for rename/change operations)
        rename_analysis: dict | None = None
        if classification.get("operation") == "rename":
            symbol_name = classification.get("symbol_name", "")
            new_name = classification.get("new_name", classification.get("new_text", ""))
            if symbol_name:
                refs = self._scan_same_file_references(
                    file_record.content or "", symbol_name, line_no
                )
                lang = self._infer_language(file_record.path)
                rename_analysis = {
                    "symbol_name": symbol_name,
                    "new_name": new_name,
                    "declaration_line": line_no,
                    "same_file_references": refs,
                    "declaration_only_rename_breaks": len(refs) > 0,
                    "full_rename_safe": True,
                    "language": lang,
                    "error_if_partial": (
                        f"error: cannot find symbol: {symbol_name}"
                        if lang == "java" else
                        f"NameError: name '{symbol_name}' is not defined"
                    ),
                }
                # Add a dedicated rename evidence block
                rename_ev_text = (
                    f"RENAME ANALYSIS for symbol '{symbol_name}' -> '{new_name}'\n"
                    f"Declaration at line {line_no}: {line_text}\n"
                    f"Same-file references after declaration ({len(refs)}):\n"
                    + ("\n".join(f"  line {r['line_no']}: {r['line_text']}" for r in refs)
                       if refs else "  (none found — rename may be safe)")
                )

        # ── Evidence block 1: exact line + broad context
        context_snippet = (
            f"FILE: {res['file_path']}\n"
            f"TARGET LINE {line_no}: {line_text}\n"
            f"ENCLOSING SCOPE: {enclosing}\n"
            f"LINE TYPE: {line_type}\n\n"
            f"--- Context before ---\n{res['context_before']}\n"
            f"--- Target line ---\n{line_no}: {line_text}\n"
            f"--- Context after ---\n{res['context_after']}"
        )
        if rename_analysis:
            refs = rename_analysis.get("same_file_references", [])
            context_snippet += (
                f"\n\n--- RENAME ANALYSIS ---\n"
                f"Symbol '{rename_analysis['symbol_name']}' declared at line {rename_analysis['declaration_line']}\n"
                f"References to '{rename_analysis['symbol_name']}' after declaration ({len(refs)}):\n"
                + ("\n".join(f"  line {r['line_no']}: {r['line_text']}" for r in refs)
                   if refs else "  (none found in this file)")
            )

        evidence = [{
            "file_id": res["file_id"],
            "file_path": res["file_path"],
            "start_line": max(1, line_no - 8),
            "end_line": line_no + 8,
            "snippet": context_snippet,
            "match_type": "impact_target",
            "score": 1.0,
        }]

        # ── Evidence block 2: enclosing symbol details
        if symbol:
            evidence.append({
                "file_path": res["file_path"],
                "snippet": (
                    f"ENCLOSING SYMBOL: {symbol.name} (type={symbol.symbol_type})\n"
                    f"Summary: {symbol.summary or 'N/A'}\n"
                    f"Lines: {symbol.start_line}–{symbol.end_line}"
                ),
                "match_type": "impact_symbol",
                "score": 0.95,
            })

            # ── Evidence block 3: caller / usage graph
            try:
                callers = self.graph_service.get_symbol_usage(repository_id, symbol.name)
                for c in callers[:5]:
                    caller_file = self.db.get(File, c.source_file_id)
                    fp = caller_file.path if caller_file else f"file_id={c.source_file_id}"
                    evidence.append({
                        "file_id": str(c.source_file_id) if c.source_file_id else None,
                        "file_path": fp,
                        "snippet": f"Symbol '{symbol.name}' is used in {fp} via {c.edge_type}",
                        "match_type": "impact_dependency",
                        "score": 0.85,
                    })
            except Exception as e:
                logger.warning(f"graph symbol_usage failed: {e}")

        # ── Evidence block 4: file importers (dependency graph)
        try:
            importers = self.graph_service.get_incoming_dependencies(file_record.id)
            for imp in importers[:5]:
                src_file = self.db.get(File, imp.source_file_id)
                if src_file:
                    evidence.append({
                        "file_id": str(src_file.id),
                        "file_path": src_file.path,
                        "snippet": f"File '{res['file_path']}' is imported/used by '{src_file.path}'",
                        "match_type": "impact_dependency",
                        "score": 0.80,
                    })
        except Exception as e:
            logger.warning(f"graph incoming_dependencies failed: {e}")

        # ── Evidence block 5: for change-impact, check if replacement symbol exists
        intent = classification.get("intent")
        if intent == QueryIntent.LINE_CHANGE_IMPACT and classification.get("operation") != "rename":
            new_text = classification.get("new_text", "")
            if new_text:
                new_sym = self.db.scalars(
                    select(Symbol).where(
                        Symbol.repository_id == repository_id,
                        Symbol.name.ilike(f"%{new_text.split('.')[-1]}%"),
                    ).limit(3)
                ).all()
                if new_sym:
                    for ns in new_sym:
                        evidence.append({
                            "file_path": "replacement_symbol_found",
                            "snippet": (
                                f"REPLACEMENT CHECK: '{new_text}' matches symbol '{ns.name}' "
                                f"({ns.symbol_type}) in repo. Replacement may be valid."
                            ),
                            "match_type": "replacement_found",
                            "score": 0.9,
                        })
                else:
                    evidence.append({
                        "file_path": "replacement_symbol_not_found",
                        "snippet": (
                            f"REPLACEMENT CHECK: '{new_text}' NOT found as any symbol in the repository. "
                            f"Replacing would likely cause NameError / AttributeError at runtime."
                        ),
                        "match_type": "replacement_missing",
                        "score": 0.9,
                    })

        # Clean up non-serializable fields before returning metadata
        line_metadata = {k: v for k, v in res.items() if k not in ("file_record", "symbol_record")}
        if rename_analysis:
            line_metadata["rename_analysis"] = rename_analysis
        return evidence, line_metadata

    @staticmethod
    def _scan_same_file_references(content: str, symbol_name: str, declaration_line: int) -> list[dict]:
        """
        Scans a file for all references to `symbol_name` after the declaration line.
        Uses word-boundary matching to avoid false positives (e.g. 'heading' vs 'headingLabel').
        Returns a list of {line_no, line_text} dicts.
        """
        import re as _re
        pattern = _re.compile(r"\b" + _re.escape(symbol_name) + r"\b")
        results = []
        for i, line in enumerate(content.splitlines(), start=1):
            if i <= declaration_line:
                continue  # skip declaration line and anything before it
            if pattern.search(line):
                stripped = line.strip()
                # Skip blank lines, comment-only lines
                if stripped and not stripped.startswith("//") and not stripped.startswith("#"):
                    results.append({"line_no": i, "line_text": stripped})
        return results

    @staticmethod
    def _infer_language(file_path: str) -> str:
        """Infers programming language from file extension."""
        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
        return {
            "java": "java", "py": "python", "js": "javascript",
            "ts": "typescript", "jsx": "javascript", "tsx": "typescript",
            "cs": "csharp", "cpp": "cpp", "c": "c", "go": "go",
            "rb": "ruby", "php": "php", "kt": "kotlin", "rs": "rust",
        }.get(ext, "unknown")

    # (Legacy stub kept for backward compat - now unused)
    def _retrieve_line_impact(self, repository_id: str, file_path_sub: str, line_no: int) -> list[dict]:
        evidence, _ = self._retrieve_line_impact_v2(
            repository_id,
            {"file": file_path_sub, "line": line_no, "snippet": None, "intent": QueryIntent.LINE_IMPACT},
            f"line {line_no} in {file_path_sub}",
        )
        return evidence



    def _retrieve_file_impact(self, repository_id: str, file_path_sub: str) -> list[dict]:
        file_record = self.db.scalar(
            select(File).where(File.repository_id == repository_id, File.path.ilike(f"%{file_path_sub}%"))
        )
        if not file_record:
            return []

        results = [{
            "file_id": file_record.id,
            "file_path": file_record.path,
            "snippet": f"FILE IMPACT TARGET: {file_record.path}. Summary: {file_record.summary or 'N/A'}",
            "score": 1.0,
            "match_type": "impact_target"
        }]

        # Who imports this file?
        importers = self.graph_service.get_incoming_dependencies(file_record.id)
        for imp in importers[:8]:
            # Load the source file path
            src_file = self.db.get(File, imp.source_file_id)
            if src_file:
                results.append({
                    "file_id": src_file.id,
                    "file_path": src_file.path,
                    "snippet": f"This file is imported/used by {src_file.path}",
                    "score": 0.9,
                    "match_type": "impact_dependency"
                })
        
        return results

    def _retrieve_dependency_trace(self, repository_id: str, target_sub: str) -> list[dict]:
        # Similar to file impact but broader
        return self._retrieve_file_impact(repository_id, target_sub)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _keyword_file_search(
        self, repository_id: str, question: str, top_k: int = 8
    ) -> list[dict]:
        """
        Final fallback: keyword search directly over File.content and EmbeddingChunk.content.
        Works even if embeddings have never been run.
        """
        tokens = [
            t.strip("?.,!:;'\"`").lower()
            for t in question.split()
            if len(t) >= 3
        ]
        # Remove trivial stop words
        stop = {"the", "is", "are", "what", "how", "does", "did", "was", "for", "can", "this", "that", "and", "not"}
        tokens = [t for t in tokens if t not in stop]
        if not tokens:
            tokens = question.lower().split()[:3]

        results: list[dict] = []

        # Search EmbeddingChunk.content (exists post-embed)
        try:
            conds = [EmbeddingChunk.content.ilike(f"%{t}%") for t in tokens[:4]]
            rows = list(
                self.db.execute(
                    select(EmbeddingChunk, File.path)
                    .outerjoin(File, File.id == EmbeddingChunk.file_id)
                    .where(
                        EmbeddingChunk.repository_id == repository_id,
                        or_(*conds),
                    )
                    .limit(top_k)
                ).all()
            )
            for chunk_row, file_path in rows:
                results.append(
                    {
                        "chunk_id": chunk_row.id,
                        "file_id": chunk_row.file_id,
                        "file_path": file_path,
                        "score": 0.6,
                        "chunk_type": chunk_row.chunk_type,
                        "start_line": chunk_row.start_line,
                        "end_line": chunk_row.end_line,
                        "snippet": chunk_row.content[:1000],
                        "match_type": "keyword",
                    }
                )
        except Exception as e:
            logger.warning(f"chunk keyword search failed: {e}")

        # Search File.content directly (works right after parse / ingest)
        try:
            fconds = [File.content.ilike(f"%{t}%") for t in tokens[:4]]
            file_rows = list(
                self.db.scalars(
                    select(File).where(
                        File.repository_id == repository_id,
                        File.content.is_not(None),
                        or_(*fconds),
                    ).limit(top_k)
                ).all()
            )
            for f in file_rows:
                results.append(
                    {
                        "chunk_id": f"filecontent:{f.id}",
                        "file_id": f.id,
                        "file_path": f.path,
                        "score": 0.55,
                        "chunk_type": "file_content",
                        "start_line": 1,
                        "end_line": min((f.line_count or 1), 200),
                        "snippet": (f.content or "")[:1000],
                        "match_type": "file_keyword",
                    }
                )
        except Exception as e:
            logger.warning(f"file content keyword search failed: {e}")

        # If no keyword hits, return top files from this repo as last resort
        if not results:
            try:
                fallback_files = list(
                    self.db.scalars(
                        select(File).where(
                            File.repository_id == repository_id,
                            File.content.is_not(None),
                        ).limit(5)
                    ).all()
                )
                for f in fallback_files:
                    results.append(
                        {
                            "chunk_id": f"file:{f.id}",
                            "file_id": f.id,
                            "file_path": f.path,
                            "score": 0.3,
                            "chunk_type": "file_content",
                            "start_line": 1,
                            "end_line": min((f.line_count or 1), 200),
                            "snippet": (f.content or "")[:1000],
                            "match_type": "fallback",
                        }
                    )
            except Exception as e:
                logger.warning(f"fallback file fetch failed: {e}")

        return results[:top_k]

    def _build_citations(self, evidence: list[dict]) -> list[dict]:
        return [
            {
                "file_id": item.get("file_id"),
                "file_path": item.get("file_path"),
                "start_line": item.get("start_line"),
                "end_line": item.get("end_line"),
                "chunk_id": item.get("chunk_id") or f"{item.get('file_path')}:{item.get('start_line')}",
                "match_type": item.get("match_type", "semantic"),
            }
            for item in evidence
        ]

    def _deterministic_answer(
        self, question: str, evidence: list[dict], intent: str = "general",
        line_metadata: dict | None = None,
    ) -> tuple[str, str, list[str]]:
        """Build a non-LLM answer grounded in evidence. Returns plain text with no markdown symbols."""
        notes: list[str] = ["Deterministic answer generated directly from structural retrieval."]

        if not evidence:
            return (
                "The requested snippet or context was not found in the repository.\n\n"
                "Running in deterministic fallback mode (LLM unavailable). "
                "Ensure the code exists in the indexed repository, or enable Gemini for richer reasoning.",
                "low",
                ["No retrieval evidence."],
            )

        # -- Rename / variable change impact — structured plain-text analysis
        ra = (line_metadata or {}).get("rename_analysis")
        if ra and intent in ("line_change_impact", "line_impact"):
            symbol_name = ra.get("symbol_name", "")
            new_name = ra.get("new_name", "")
            decl_line = ra.get("declaration_line", "?")
            refs = ra.get("same_file_references", [])
            lang = ra.get("language", "unknown")
            error_msg = ra.get("error_if_partial", f"cannot find symbol: {symbol_name}")
            file_path = (line_metadata or {}).get("file_path", "unknown")
            confidence = "high" if refs is not None else "medium"

            sections: list[str] = []
            sections.append(f"Operation: rename '{symbol_name}' to '{new_name}'")
            sections.append(f"Resolved File: {file_path}")
            sections.append(f"Declaration Line: {decl_line}")
            sections.append(f"Language: {lang}")
            sections.append("")

            if refs:
                sections.append(
                    f"CASE A — Declaration-only rename (BREAKS):\n"
                    f"If you rename only the declaration on line {decl_line} but leave "
                    f"references unchanged, the compiler will report:\n"
                    f"  {error_msg}\n"
                    f"\nLines that still reference '{symbol_name}' ({len(refs)} found):"
                )
                for r in refs:
                    sections.append(f"  Line {r['line_no']}: {r['line_text']}")
                sections.append("")
                sections.append(
                    f"CASE B — Full consistent rename (SAFE):\n"
                    f"If you rename '{symbol_name}' to '{new_name}' on ALL {len(refs) + 1} lines "
                    f"(declaration + {len(refs)} references), this is a safe refactor with "
                    f"no functional or behavioral change."
                )
            else:
                sections.append(
                    f"No references to '{symbol_name}' found after line {decl_line} in this file.\n"
                    f"Renaming only the declaration appears safe — no same-file references break.\n"
                    f"Check cross-file usages if this symbol is public/exported."
                )

            sections.append("")
            sections.append(f"Confidence: {confidence.upper()}")

            key_files = list(dict.fromkeys(
                e.get("file_path", "unknown") for e in evidence if e.get("file_path")
            ))
            sections.append(f"Evidence from: {', '.join(key_files[:3])}")

            return "\n".join(sections), confidence, notes

        # -- REPO SUMMARY — structured plain-text repository overview
        if intent == QueryIntent.REPO_SUMMARY:
            parts: list[str] = []
            confidence = "high" if len(evidence) >= 3 else "medium"

            # Extract data from evidence tiers
            repo_summary_text = ""
            primary_language = "unknown"
            frameworks: list[str] = []
            entrypoints: list[str] = []
            readme_text = ""
            file_types_line = ""
            total_files = 0

            for e in evidence:
                mt = e.get("match_type", "")
                snippet = e.get("snippet", "") or ""
                fp = e.get("file_path", "") or ""

                if mt == "repo_metadata":
                    if "REPOSITORY SUMMARY" in snippet:
                        repo_summary_text = snippet.replace("REPOSITORY SUMMARY (from parse stage):\n", "").strip()[:600]
                    if "Primary Language:" in snippet:
                        for line in snippet.splitlines():
                            if line.startswith("Primary Language:"):
                                primary_language = line.split(":", 1)[-1].strip()
                            elif line.startswith("Framework:"):
                                fw = line.split(":", 1)[-1].strip()
                                if fw:
                                    frameworks.append(fw)
                elif mt == "structure_census":
                    for line in snippet.splitlines():
                        if "Total files indexed:" in line:
                            try:
                                total_files = int(line.split(":")[-1].strip())
                            except Exception:
                                pass
                        elif "File types:" in line:
                            file_types_line = line.split(":", 1)[-1].strip()
                        elif "Detected entrypoints:" in line:
                            ep = line.split(":", 1)[-1].strip()
                            if ep and ep != "none detected":
                                entrypoints.extend(ep.split(", "))
                elif mt == "readme":
                    if not readme_text:
                        # Take first ~500 chars of README, excluding the file path header
                        body = snippet
                        if fp in body:
                            body = body.replace(f"DOCUMENTATION FILE: {fp}\n", "").strip()
                        readme_text = body[:500]
                elif mt == "entrypoint":
                    fname = fp.split("/")[-1]
                    if fname not in entrypoints:
                        entrypoints.append(fp)

            # Guess complexity from file count
            if total_files <= 5:
                complexity = "starter / demo project"
            elif total_files <= 20:
                complexity = "small project"
            elif total_files <= 80:
                complexity = "mid-size project"
            else:
                complexity = "production-scale project"

            # Build the answer
            parts.append("Repository Overview")
            parts.append("=" * 40)

            if repo_summary_text:
                parts.append(f"\nSummary:\n{repo_summary_text}")
            elif readme_text:
                parts.append(f"\nFrom README:\n{readme_text}")
            else:
                parts.append("\nNo README or stored summary found.")

            parts.append(f"\nPrimary Language: {primary_language}")
            parts.append(f"Frameworks / Tools: {', '.join(frameworks) if frameworks else 'not detected'}")
            parts.append(f"Total Files Indexed: {total_files if total_files else 'unknown'}")
            parts.append(f"File Types: {file_types_line or 'unknown'}")

            if entrypoints:
                parts.append(f"\nDetected Entrypoints:")
                for ep in entrypoints[:5]:
                    parts.append(f"  {ep}")
            else:
                parts.append("\nEntrypoints: none detected in indexed files")

            parts.append(f"\nProject Scale: {complexity}")
            parts.append(f"\nConfidence: {confidence.upper()}")
            parts.append(f"Evidence: {len(evidence)} evidence blocks (README, metadata, entrypoints)")

            return "\n".join(parts), confidence, notes

        # -- Generic deterministic answer (clean plain text)
        top = evidence[:6]
        confidence = "high" if len(top) >= 3 else "medium"

        match_types = list(set([e.get("match_type", "unknown") for e in top]))
        if "impact_target" in match_types or "impact_dependency" in match_types:
            answer_summary = "Isolated exact code paths and downstream dependencies related to your query."
        elif "impact_symbol" in match_types:
            answer_summary = "Tracked the specific symbol hierarchy to provide bounded context."
        else:
            answer_summary = "Retrieved directly relevant repository files for this query."

        gen_parts: list[str] = [answer_summary, ""]
        gen_parts.append("Key files:")
        key_files = list(dict.fromkeys([e.get("file_path", "unknown") for e in top]))
        for fp in key_files:
            gen_parts.append(f"  {fp}")

        gen_parts.append(f"\nConfidence: {confidence.upper()} (from {len(top)} evidence hits)")
        gen_parts.append("\nEvidence:")
        for e in top:
            fp = e.get("file_path") or "unknown"
            sl = e.get("start_line")
            el = e.get("end_line")
            mt = e.get("match_type", "")
            loc = f"{fp}:{sl}-{el}" if sl and el else fp
            preview = (e.get("snippet") or "").strip().splitlines()[:2]
            preview_text = " ".join(s.strip() for s in preview if s.strip())[:180]
            gen_parts.append(f"  [{mt.upper()}] {loc} — {preview_text}")

        return "\n".join(gen_parts), confidence, notes
