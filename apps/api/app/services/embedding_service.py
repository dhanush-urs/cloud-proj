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

        files = list(
            self.db.scalars(
                select(File).where(
                    File.repository_id == repository.id,
                    File.parse_status.in_(["parsed", "pending", "skipped"]),
                )
            ).all()
        )

        total_chunks = 0
        processed_files = 0

        for file_record in files:
            if file_record.file_kind not in {"source", "test", "config", "build", "script", "doc"}:
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
                    "snippet": chunk_row.content[:1000],
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def hybrid_search(
        self,
        repository_id: str,
        query: str,
        top_k: int = 8,
    ) -> list[dict]:
        """
        Generalized Hybrid Search for ANY repository:
        1. Query Mode Detection (Code vs Natural Language)
        2. Exact Substring Match (Case-sensitive & Insensitive)
        3. Path Matches (Filename priority)
        4. Semantic Matches (Vector fallback)
        5. Noise Filtering (Exclude lockfiles & vendor)
        6. Compact Snippets (Centered on match)
        """
        # --- 1. Query Mode Detection ---
        # Detect if it looks like code (dots, slashes, underscores, backticks, camelCase)
        is_code_query = any(c in query for c in {".", "/", "_", "(", ")", ":", "{"}) or \
                        any(word[0].islower() and any(c.isupper() for c in word[1:]) for word in query.split())
        
        # --- 2. Noise Filtering Patterns ---
        NOISE_PATTERNS = [
            "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "vendor/", 
            "node_modules/", ".min.js", ".map", "dist/", "build/", ".next/"
        ]

        def _is_noisy(path: str) -> bool:
            if not path: return False
            p = path.lower()
            return any(n in p for n in NOISE_PATTERNS)

        # --- 3. Exact Substring Search (Highest Priority) ---
        exact_results = []
        if len(query) >= 3:
            # Case-sensitive exact match in File content
            exact_files = list(self.db.scalars(
                select(File).where(
                    File.repository_id == repository_id,
                    File.content.contains(query)
                ).limit(5)
            ).all())
            
            for f in exact_files:
                if _is_noisy(f.path): continue
                snippet, start, end = self._get_compact_snippet(f.content or "", query)
                exact_results.append({
                    "chunk_id": f"exact:{f.id}:{start}",
                    "file_id": f.id,
                    "file_path": f.path,
                    "score": 1.0,
                    "chunk_type": "exact_match",
                    "start_line": start,
                    "end_line": end,
                    "snippet": snippet,
                    "match_type": "exact",
                })

            # Case-insensitive if no exact sensitive matches or if it's a code query
            if not exact_results or is_code_query:
                ci_files = list(self.db.scalars(
                    select(File).where(
                        File.repository_id == repository_id,
                        File.content.ilike(f"%{query}%")
                    ).limit(5)
                ).all())
                for f in ci_files:
                    if _is_noisy(f.path) or any(r["file_id"] == f.id for r in exact_results):
                        continue
                    snippet, start, end = self._get_compact_snippet(f.content or "", query, case_sensitive=False)
                    exact_results.append({
                        "chunk_id": f"exact_ci:{f.id}:{start}",
                        "file_id": f.id,
                        "file_path": f.path,
                        "score": 0.95,
                        "chunk_type": "exact_match_ci",
                        "start_line": start,
                        "end_line": end,
                        "snippet": snippet,
                        "match_type": "exact_ci",
                    })

        # --- 4. Semantic Search ---
        semantic = []
        try:
            semantic = self.semantic_search(repository_id, query, top_k=top_k)
            filtered_semantic = []
            for r in semantic:
                if _is_noisy(r.get("file_path")): 
                    continue # Drop noisy semantic matches
                r["match_type"] = "semantic"
                filtered_semantic.append(r)
            semantic = filtered_semantic
        except Exception as e:
            print(f"semantic_search failed in hybrid_search: {e}")

        # --- 5. Path matches ---
        path_rows = []
        tokens = [t.strip("?.,!:;'\"`").lower() for t in query.split() if len(t) >= 3]
        candidates = [t for t in tokens if "/" in t or "." in t or len(t) > 5]
        if candidates:
            conds = [File.path.ilike(f"%{c}%") for c in candidates[:3]]
            files = list(self.db.scalars(
                select(File).where(File.repository_id == repository_id, or_(*conds)).limit(5)
            ).all())
            for f in files:
                if _is_noisy(f.path): continue
                path_rows.append({
                    "chunk_id": f"path:{f.id}",
                    "file_id": f.id,
                    "file_path": f.path,
                    "score": 0.9,
                    "chunk_type": "file_path",
                    "start_line": 1,
                    "end_line": min((f.line_count or 20), 20),
                    "snippet": (f.content or "")[:1000],
                    "match_type": "path",
                })

        # --- 6. Merge & Deduplicate ---
        merged = []
        seen_chunk: set[str] = set()
        seen_loc: set[str] = set()
        
        # Priority: Exact > Path > Semantic
        for r in exact_results + path_rows + semantic:
            cid = str(r.get("chunk_id"))
            loc = f"{r.get('file_path')}:{r.get('start_line')}"
            if cid in seen_chunk or loc in seen_loc:
                continue
            seen_chunk.add(cid)
            seen_loc.add(loc)
            merged.append(r)

        merged.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return merged[:top_k]

    def _get_compact_snippet(self, content: str, query: str, context_lines: int = 7, case_sensitive: bool = True) -> tuple[str, int, int]:
        """Extracts a compact snippet (max ~15 lines) centered on the first match of query."""
        if not content:
            return "", 1, 1
        
        lines = content.splitlines()
        match_line_idx = -1
        
        query_to_find = query if case_sensitive else query.lower()
        
        for i, line in enumerate(lines):
            line_to_check = line if case_sensitive else line.lower()
            if query_to_find in line_to_check:
                match_line_idx = i
                break
        
        if match_line_idx == -1:
            return "\n".join(lines[:15]), 1, min(15, len(lines))
            
        start = max(0, match_line_idx - context_lines)
        end = min(len(lines), match_line_idx + context_lines + 1)
        
        snippet = "\n".join(lines[start:end])
        return snippet, start + 1, end

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
