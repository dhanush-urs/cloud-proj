from pathlib import Path

from sqlalchemy import delete, func, select, or_
from sqlalchemy.orm import Session

from app.db.models.embedding_chunk import EmbeddingChunk
from app.db.models.file import File
from app.db.models.repo_snapshot import RepoSnapshot
from app.db.models.repository import Repository
from app.embeddings.chunker import Chunker
from app.embeddings.embedding_engine import LocalEmbeddingEngine
from app.llm.providers import get_embedding_provider, get_chat_provider
from app.utils.path_utils import normalize_repo_snapshot_path


class EmbeddingService:
    def __init__(self, db: Session):
        self.db = db
        self.chunker = Chunker()
        self.provider = get_embedding_provider()
        self.chat_provider = get_chat_provider()
        self.local_engine = LocalEmbeddingEngine()

    def _get_repo_root(self, repository: Repository) -> Path | None:
        snapshot = self.db.scalar(
            select(RepoSnapshot)
            .where(RepoSnapshot.repository_id == repository.id)
            .order_by(RepoSnapshot.created_at.desc())
            .limit(1)
        )

        if not snapshot:
            return None

        return normalize_repo_snapshot_path(snapshot.local_path)

    def embed_repository(self, repository: Repository) -> dict:
        repo_root = self._get_repo_root(repository)
        if not repo_root:
            raise ValueError("No repository snapshot found")

        self.db.execute(
            delete(EmbeddingChunk).where(EmbeddingChunk.repository_id == repository.id)
        )
        self.db.commit()

        # Embed files that either made it through parse, or are pure extracted content
        files = list(
            self.db.scalars(
                select(File).where(
                    File.repository_id == repository.id,
                    File.parse_status.in_(["parsed", "content_extracted"]),
                )
            ).all()
        )

        total_chunks = 0
        processed_files = 0

        for file_record in files:
            # Embed all text-like file kinds — not just source/config
            _EMBEDDABLE_KINDS = {
                "source", "test", "config", "build", "script", "doc",
                "markup", "style", "data", "unknown",
            }
            if file_record.file_kind not in _EMBEDDABLE_KINDS:
                # Pure binary assets (images, fonts, archives)
                continue

            if file_record.is_vendor or file_record.is_generated:
                continue

            file_path = repo_root / file_record.path
            if not file_path.exists() or not file_path.is_file():
                continue

            chunks = self.chunker.chunk_file(file_path)
            if not chunks:
                continue

            for chunk in chunks:
                vector = self.provider.embed_text(chunk["content"])

                chunk_row = EmbeddingChunk(
                    repository_id=repository.id,
                    file_id=file_record.id,
                    chunk_type=chunk["chunk_type"],
                    content=chunk["content"],
                    start_line=chunk.get("start_line"),
                    end_line=chunk.get("end_line"),
                    embedding_model=self.provider.model_name,
                    embedding_vector=self.local_engine.serialize(vector),
                )
                self.db.add(chunk_row)
                total_chunks += 1

            processed_files += 1

        self.db.commit()

        return {
            "processed_files": processed_files,
            "total_chunks": total_chunks,
            "embedding_model": self.provider.model_name,
        }

    def semantic_search(
        self,
        repository_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        query_vector = self.provider.embed_text(query)

        rows = list(
            self.db.execute(
                select(EmbeddingChunk, File.path)
                .outerjoin(File, File.id == EmbeddingChunk.file_id)
                .where(EmbeddingChunk.repository_id == repository_id)
            ).all()
        )

        scored = []

        for chunk_row, file_path in rows:
            # Skip rows created with a different embedding model to avoid dimension/scale issues
            if chunk_row.embedding_model != self.provider.model_name:
                continue

            chunk_vector = self.local_engine.deserialize(chunk_row.embedding_vector)

            if len(query_vector) != len(chunk_vector):
                continue

            score = self.local_engine.cosine_similarity(query_vector, chunk_vector)

            scored.append(
                {
                    "chunk_id": chunk_row.id,
                    "file_id": chunk_row.file_id,
                    "file_path": file_path,
                    "score": score,
                    "chunk_type": chunk_row.chunk_type,
                    "start_line": chunk_row.start_line,
                    "end_line": chunk_row.end_line,
                    "snippet": self._get_bounded_preview(chunk_row.content, max_lines=25, query=query)[0],
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def hybrid_search(
        self,
        repository_id: str,
        query: str,
        top_k: int = 8,
        mode: str = "general",
    ) -> list[dict]:
        """
        Generalized Hybrid Search for ANY repository:
        1. Query Mode Detection (Code vs Natural Language)
        2. Exact Substring Match (Case-sensitive & Insensitive)
        3. Token-level Match boosting (Highest priority for symbols)
        4. Path Matches (Filename priority)
        5. Semantic Matches (Vector fallback - skipped if mode='lexical_only')
        6. Noise Filtering (Exclude lockfiles & vendor)
        7. Compact Snippets (Centered on match)
        """
        is_lexical_only = mode == "lexical_only"
        
        # --- 1. Query Mode Detection ---
        code_keywords = {"import", "from", "class", "async", "await", "return", "public", "private", "export", "def", "function", "var", "let", "const"}
        is_code_query = any(c in query for c in {".", "/", "_", "(", ")", ":", "{", "}", "`", "=", ">", "<"}) or \
                        any(word[0].islower() and any(c.isupper() for c in word[1:]) for word in query.split()) or \
                        any(k in query.split() for k in code_keywords)
        
        # --- 2. Noise Filtering Patterns ---
        NOISE_PATTERNS = [
            "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "vendor/", 
            "node_modules/", ".min.js", ".map", "dist/", "build/", ".next/", "__pycache__"
        ]

        def _is_noisy(path: str) -> bool:
            if not path: return False
            p = path.lower()
            return any(n in p for n in NOISE_PATTERNS)

        # --- 3. Exact Substring & Token Search (Highest Priority) ---
        exact_results = []
        if len(query) >= 2:
            exact_files = list(self.db.scalars(
                select(File).where(
                    File.repository_id == repository_id,
                    File.content.ilike(f"%{query}%")
                ).limit(10)
            ).all())
            
            import re
            # Token pattern: match the query surrounded by non-word boundaries or starts/ends of lines
            token_pattern = re.compile(rf"(^|[^a-zA-Z0-9_]){re.escape(query)}([^a-zA-Z0-9_]|$)", re.IGNORECASE)

            for f in exact_files:
                if _is_noisy(f.path): continue
                
                content = f.content or ""
                snippet, start, end, matched_lines = self._get_compact_snippet(content, query, case_sensitive=(query in content))
                
                # Boost if it's an exact TOKEN match (e.g. variable name) vs just a substring match
                is_token = bool(token_pattern.search(content))
                score = 1.0 if is_token else 0.85
                
                # Case-sensitivity boost
                if query in content:
                    score += 0.05

                exact_results.append({
                    "chunk_id": f"token:{f.id}:{start}" if is_token else f"substring:{f.id}:{start}",
                    "file_id": f.id,
                    "file_path": f.path,
                    "score": score,
                    "chunk_type": "token_match" if is_token else "substring_match",
                    "start_line": start,
                    "end_line": end,
                    "matched_lines": matched_lines,
                    "snippet": snippet,
                    "match_type": "exact",
                })


        # --- 4. Semantic Search ---
        semantic = []
        if not is_lexical_only:
            try:
                semantic = self.semantic_search(repository_id, query, top_k=top_k)
                filtered_semantic = []
                for r in semantic:
                    if _is_noisy(r.get("file_path")): continue
                    r["match_type"] = "semantic"
                    # If it's a code query, downgrade semantic scores slightly if they don't have token overlap
                    filtered_semantic.append(r)
                semantic = filtered_semantic
            except Exception as e:
                print(f"semantic_search failed in hybrid_search: {e}")

        # --- 5. Path matches ---
        path_rows = []
        query_path = query.lower().strip("/")
        if len(query_path) >= 3:
            path_files = list(self.db.scalars(
                select(File).where(
                    File.repository_id == repository_id,
                    File.path.ilike(f"%{query_path}%")
                ).limit(5)
            ).all())
            for f in path_files:
                if _is_noisy(f.path): continue
                # Exact filename match gets very high score
                path_score = 0.98 if f.path.lower().endswith(query_path.lower()) else 0.9
                path_rows.append({
                    "chunk_id": f"path:{f.id}",
                    "file_id": f.id,
                    "file_path": f.path,
                    "score": path_score,
                    "chunk_type": "file_path",
                    "start_line": 1,
                    "end_line": min((f.line_count or 20), 20),
                    "snippet": self._get_bounded_preview(f.content or "", max_lines=25, query=query_path)[0],
                    "match_type": "path",
                })

        # --- 6. Merge & Filter ---
        merged = []
        seen_chunk: set[str] = set()
        seen_loc: set[str] = set()

        # Priority: Exact/Token > Path > Semantic
        # We sort them into a unified list, keeping only the best match per location.
        all_candidates = exact_results + path_rows + semantic
        all_candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)

        # Identity tokens for strict filtering of semantic noise
        query_words = [t.strip("?.,!:;'\"`").lower() for t in query.split()]
        identity_tokens = [t for t in query_words if len(t) >= 4 and t not in code_keywords]

        for r in all_candidates:
            cid = str(r.get("chunk_id"))
            loc = f"{r.get('file_path')}:{r.get('start_line')}"
            if cid in seen_chunk or loc in seen_loc:
                continue
            
            # Strict Filtering for Semantic Fallback in code mode
            if r.get("match_type") == "semantic" and exact_results and is_code_query:
                snippet_lower = r.get("snippet", "").lower()
                path_lower = r.get("file_path", "").lower()
                has_overlap = any(t in snippet_lower or t in path_lower for t in identity_tokens)
                if not has_overlap and len(identity_tokens) > 0:
                    continue # Drop irrelevant semantic hallucination

            seen_chunk.add(cid)
            seen_loc.add(loc)
            merged.append(r)

        # 7. Post-Merge Filtering (Noise Suppression)
        final_results = []
        has_high_confidence = any(r.get("score", 0.0) >= 0.85 for r in merged)
        
        for r in merged:
            # Drop low-relevance CODE_WINDOW noise if we have high-quality matches
            if has_high_confidence and r.get("chunk_type") == "code_window" and r.get("score", 0.0) < 0.4:
                continue
            # Drop extreme semantic outliers (mostly hallucinated noise in large indexes)
            if r.get("match_type") == "semantic" and r.get("score", 0.0) < 0.2:
                continue
            final_results.append(r)

        return final_results[:top_k]

    def _get_bounded_preview(self, full_text: str, focus_line: int | None = None, radius: int = 8, max_lines: int = 25, query: str | None = None) -> tuple[str, int, int]:
        """Returns a tightly bounded snippet restricted strictly to max_lines.
        If focus_line is provided, centers around it. 
        If focus_line is None but query is provided, tries to find first occurrence.
        Outputs: (preview_text, start_line, end_line)"""
        if not full_text:
            return "", 1, 1
            
        lines = full_text.splitlines()
        total_lines = len(lines)
        
        if total_lines <= max_lines:
            return full_text, 1, total_lines
            
        # Try to find a good focus center if not provided
        if focus_line is None:
            if query and len(query) >= 3:
                q_lower = query.lower()
                for i, line in enumerate(lines):
                    if q_lower in line.lower():
                        focus_line = i + 1
                        break
            
            if focus_line is None:
                # Default to start for very small snippets or middle for semantic chunks
                focus_line = 1 if total_lines < 100 else (total_lines // 2)

        focus_idx = focus_line - 1
        start_idx = max(0, focus_idx - radius)
        # Ensure we capture at least max_lines if possible
        end_idx = min(total_lines, start_idx + max_lines)
        
        # Shift start if we reached bottom but have room at top
        if (end_idx - start_idx) < max_lines:
            start_idx = max(0, end_idx - max_lines)

        snippet = "\n".join(lines[start_idx:end_idx])
        return snippet, start_idx + 1, end_idx

        snippet = "\n".join(lines[start_idx:end_idx])
        return snippet, start_idx + 1, end_idx

    def _get_compact_snippet(self, content: str, query: str, context_lines: int = 7, case_sensitive: bool = True) -> tuple[str, int, int, list[int]]:
        """Extracts a compact snippet centered on the first match, and identifies ALL matching lines."""
        if not content:
            return "", 1, 1, []
        
        lines = content.splitlines()
        match_line_indices = []
        
        query_to_find = query if case_sensitive else query.lower()
        
        for i, line in enumerate(lines):
            line_to_check = line if case_sensitive else line.lower()
            if query_to_find in line_to_check:
                match_line_indices.append(i + 1) # 1-indexed
        
        # Use the new bounded preview helper for exact matches
        focus_line = match_line_indices[0] if match_line_indices else 1
        snippet, start_line, end_line = self._get_bounded_preview(content, focus_line=focus_line, radius=context_lines, max_lines=(context_lines * 2) + 1)
        
        # Identify which of the match_line_indices fall within this window
        matched_in_window = [idx for idx in match_line_indices if start_line <= idx <= end_line]
        
        return snippet, start_line, end_line, matched_in_window


    def ask_repo(
        self,
        repository_id: str,
        question: str,
        top_k: int = 5,
    ) -> dict:
        results = self.semantic_search(repository_id, question, top_k=top_k)

        if not results:
            return {
                "answer": (
                    "I could not find compatible embedded code context for this repository. "
                    "If you recently changed EMBEDDING_PROVIDER, re-run the /embed pipeline."
                ),
                "citations": [],
            }

        # Synthesis via Gemini if enabled and available
        from app.core.config import get_settings
        settings = get_settings()
        
        answer = None
        mode = "grounded_template"
        
        if settings.ENABLE_GEMINI and self.chat_provider:
            try:
                context_str = "\n---\n".join(
                    [f"FILE: {r['file_path']}\nCONTENT:\n{r['snippet']}" for r in results]
                )
                system_prompt = (
                    "You are RepoBrain, a technical assistant. Answer the user's question based ONLY on the provided code context. "
                    "Be technical, concise, and accurate. If the answer isn't in the context, say so gracefully."
                )
                user_prompt = f"Question: {question}\n\nContext:\n{context_str}"
                
                synthesis = self.chat_provider.answer(system_prompt, user_prompt)
                if synthesis:
                    answer = synthesis
                    mode = "gemini_synthesis"
            except Exception as e:
                print(f"[WARN] Gemini synthesis failed, falling back to grounded template: {e}")

        if not answer:
            answer = self._build_grounded_answer(question, results)

        citations = [
            {
                "file_id": item["file_id"],
                "file_path": item["file_path"],
                "start_line": item["start_line"],
                "end_line": item["end_line"],
                "chunk_id": item["chunk_id"],
            }
            for item in results
        ]

        return {
            "answer": answer,
            "citations": citations,
            "mode": mode,
            "llm_model": self.chat_provider.model_name if mode == "gemini_synthesis" else None,
        }

    def _build_grounded_answer(self, question: str, results: list[dict]) -> str:
        question_lower = question.lower()
        top = results[:3]

        if any(word in question_lower for word in ["auth", "authentication", "login", "signin", "sign in"]):
            intro = "Based on the indexed code, authentication-related logic appears to be concentrated in these files/chunks:"
        elif any(word in question_lower for word in ["route", "api", "endpoint"]):
            intro = "Based on the indexed code, API/route-related logic appears most relevant in these files/chunks:"
        elif any(word in question_lower for word in ["config", "setting", "env"]):
            intro = "Based on the indexed code, configuration-related logic appears most relevant in these files/chunks:"
        else:
            intro = "Based on the most relevant indexed code chunks, the best matching implementation areas are:"

        bullets = []
        for item in top:
            location = item["file_path"] or "unknown file"
            line_info = ""
            if item["start_line"] and item["end_line"]:
                line_info = f" (lines {item['start_line']}-{item['end_line']})"

            snippet_preview = item["snippet"].splitlines()[:3]
            preview = " ".join(line.strip() for line in snippet_preview if line.strip())
            preview = preview[:180]

            bullets.append(f"- {location}{line_info}: {preview}")

        closing = (
            "Use the cited chunks as the primary evidence. "
            "For a stronger answer, ask a narrower question or re-run the embedding pipeline if you switch models."
        )

        return "\n".join([intro, *bullets, closing])

    def list_chunks(
        self,
        repository_id: str,
        file_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[EmbeddingChunk], int]:
        base_stmt = select(EmbeddingChunk).where(EmbeddingChunk.repository_id == repository_id)

        if file_id:
            base_stmt = base_stmt.where(EmbeddingChunk.file_id == file_id)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        stmt = (
            base_stmt
            .order_by(EmbeddingChunk.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        items = list(self.db.scalars(stmt).all())
        return items, total

    def embed_single_file(self, repository_id: str, file_id: str) -> None:
        file_row = self.db.scalar(
            select(File).where(
                File.repository_id == repository_id,
                File.id == file_id,
            )
        )

        if not file_row or not file_row.content:
            return

        # Clear previous chunks for this file
        self.db.execute(
            delete(EmbeddingChunk).where(
                EmbeddingChunk.repository_id == repository_id,
                EmbeddingChunk.file_id == file_id,
            )
        )
        self.db.commit()

        # Simple chunking for incremental updates
        chunks = self._simple_chunk_text(file_row.content, max_lines=80, overlap=10)

        for idx, chunk in enumerate(chunks):
            chunk_text = chunk["content"]
            vector = self.provider.embed_text(chunk_text)

            embedding_chunk = EmbeddingChunk(
                repository_id=repository_id,
                file_id=file_id,
                chunk_type="code",
                content=chunk_text,
                start_line=chunk["start_line"],
                end_line=chunk["end_line"],
                embedding_model=self.provider.model_name,
                embedding_vector=self.local_engine.serialize(vector),
            )

            self.db.add(embedding_chunk)

        self.db.commit()

    def _simple_chunk_text(self, content: str, max_lines: int = 80, overlap: int = 10) -> list[dict]:
        lines = content.splitlines()
        chunks = []

        if not lines:
            return []

        start = 0
        while start < len(lines):
            end = min(start + max_lines, len(lines))
            chunk_lines = lines[start:end]

            chunks.append(
                {
                    "content": "\n".join(chunk_lines),
                    "start_line": start + 1,
                    "end_line": end,
                }
            )

            if end >= len(lines):
                break

            start = max(0, end - overlap)

        return chunks
