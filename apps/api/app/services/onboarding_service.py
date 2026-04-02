from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.dependency_edge import DependencyEdge
from app.db.models.file import File
from app.db.models.onboarding_document import OnboardingDocument
from app.db.models.repository import Repository
from app.db.models.symbol import Symbol
from app.llm.providers import get_chat_provider
from app.services.embedding_service import EmbeddingService
from app.services.risk_service import RiskService


class OnboardingService:
    def __init__(self, db: Session):
        self.db = db
        self.risk_service = RiskService(db)
        self.embedding_service = EmbeddingService(db)

    def generate_document(
        self,
        repository: Repository,
        top_files: int = 10,
        include_hotspots: bool = True,
        include_search_context: bool = True,
    ) -> OnboardingDocument:
        context = self._build_repo_context(
            repository_id=repository.id,
            top_files=top_files,
            include_hotspots=include_hotspots,
            include_search_context=include_search_context,
        )

        chat_provider = get_chat_provider()

        if chat_provider:
            try:
                content = self._generate_with_llm(
                    repository=repository,
                    context=context,
                )

                mode = "llm"
                llm_model = chat_provider.model_name
            except Exception:
                content = self._generate_deterministic_markdown(repository, context)
                mode = "deterministic_fallback"
                llm_model = None
        else:
            content = self._generate_deterministic_markdown(repository, context)
            mode = "deterministic"
            llm_model = None

        latest_version = self.db.scalar(
            select(func.max(OnboardingDocument.version)).where(
                OnboardingDocument.repository_id == repository.id
            )
        ) or 0

        doc = OnboardingDocument(
            repository_id=repository.id,
            version=latest_version + 1,
            title="Repository Onboarding Guide",
            content_markdown=content,
            generation_mode=mode,
            llm_model=llm_model,
        )

        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        return doc

    def get_latest_document(self, repository_id: str) -> OnboardingDocument | None:
        return self.db.scalar(
            select(OnboardingDocument)
            .where(OnboardingDocument.repository_id == repository_id)
            .order_by(OnboardingDocument.version.desc(), OnboardingDocument.created_at.desc())
            .limit(1)
        )

    def _build_repo_context(
        self,
        repository_id: str,
        top_files: int,
        include_hotspots: bool,
        include_search_context: bool,
    ) -> dict:
        files = list(
            self.db.scalars(
                select(File).where(File.repository_id == repository_id)
            ).all()
        )

        file_ids = [f.id for f in files]

        symbol_counts = dict(
            self.db.execute(
                select(Symbol.file_id, func.count(Symbol.id))
                .where(Symbol.repository_id == repository_id)
                .group_by(Symbol.file_id)
            ).all()
        )

        outbound_counts = dict(
            self.db.execute(
                select(DependencyEdge.source_file_id, func.count(DependencyEdge.id))
                .where(
                    DependencyEdge.repository_id == repository_id,
                    DependencyEdge.source_file_id.in_(file_ids) if file_ids else False,
                )
                .group_by(DependencyEdge.source_file_id)
            ).all()
        ) if file_ids else {}

        inbound_counts = dict(
            self.db.execute(
                select(DependencyEdge.target_file_id, func.count(DependencyEdge.id))
                .where(
                    DependencyEdge.repository_id == repository_id,
                    DependencyEdge.target_file_id.in_(file_ids) if file_ids else False,
                )
                .group_by(DependencyEdge.target_file_id)
            ).all()
        ) if file_ids else {}

        important_files = []

        for file in files:
            if file.file_kind not in {"source", "config", "build", "script", "test"}:
                continue

            score = (
                min((file.line_count or 0) / 15.0, 20.0)
                + min(symbol_counts.get(file.id, 0) * 2.0, 25.0)
                + min(inbound_counts.get(file.id, 0) * 4.0, 25.0)
                + min(outbound_counts.get(file.id, 0) * 2.5, 15.0)
            )

            if self._is_likely_entrypoint(file.path):
                score += 18.0

            important_files.append(
                {
                    "file_id": file.id,
                    "path": file.path,
                    "language": file.language,
                    "file_kind": file.file_kind,
                    "line_count": file.line_count or 0,
                    "symbol_count": int(symbol_counts.get(file.id, 0)),
                    "inbound_dependencies": int(inbound_counts.get(file.id, 0)),
                    "outbound_dependencies": int(outbound_counts.get(file.id, 0)),
                    "importance_score": round(score, 2),
                    "is_likely_entrypoint": self._is_likely_entrypoint(file.path),
                }
            )

        important_files.sort(key=lambda x: x["importance_score"], reverse=True)
        important_files = important_files[:top_files]

        hotspots = []
        if include_hotspots:
            hotspots = self.risk_service.get_hotspots(repository_id=repository_id, limit=8)

        search_context = []
        if include_search_context:
            questions = [
                "Where is application initialization handled?",
                "Which files look central to routing or request handling?",
                "Which configuration files are important?",
            ]

            for q in questions:
                # Note: semantic_search might be async in some implementations, but here it is assumed synchronous via EmbeddingService
                results = self.embedding_service.semantic_search(
                    repository_id=repository_id,
                    query=q,
                    top_k=3,
                )
                if results:
                    search_context.append(
                        {
                            "question": q,
                            "results": results,
                        }
                    )

        entrypoints = [f for f in important_files if f["is_likely_entrypoint"]][:5]
        config_files = [f for f in important_files if f["file_kind"] in {"config", "build"}][:5]
        source_files = [f for f in important_files if f["file_kind"] == "source"][:8]

        languages = sorted({f.language for f in files if f.language})

        return {
            "languages": languages,
            "file_count": len(files),
            "important_files": important_files,
            "entrypoints": entrypoints,
            "config_files": config_files,
            "source_files": source_files,
            "hotspots": hotspots,
            "search_context": search_context,
        }

    def _generate_with_llm(self, repository: Repository, context: dict) -> str:
        chat_provider = get_chat_provider()
        if not chat_provider:
            raise ValueError("No chat provider available")

        system_prompt = (
            "You are RepoBrain, an expert repository onboarding assistant. "
            "Generate a markdown onboarding guide for a new engineer joining this project. "
            "Use only the provided structured repository context. "
            "Do not invent files, modules, or behaviors not present in the context. "
            "Keep the guide practical, technical, and easy to scan."
        )

        user_prompt = self._build_llm_prompt(repository, context)

        content = chat_provider.answer(system_prompt, user_prompt).strip()
        if not content:
            raise ValueError("Empty LLM response")

        return content

    def _build_llm_prompt(self, repository: Repository, context: dict) -> str:
        important_files_lines = "\n".join(
            [
                f"- {f['path']} | kind={f['file_kind']} | lang={f['language']} | "
                f"lines={f['line_count']} | symbols={f['symbol_count']} | "
                f"in={f['inbound_dependencies']} | out={f['outbound_dependencies']} | "
                f"entrypoint={f['is_likely_entrypoint']}"
                for f in context["important_files"]
            ]
        ) or "- None"

        hotspot_lines = "\n".join(
            [
                f"- {h['path']} | risk={h['risk_score']} | level={h['risk_level']} | "
                f"symbols={h['symbol_count']} | in={h['inbound_dependencies']} | out={h['outbound_dependencies']}"
                for h in context["hotspots"]
            ]
        ) or "- None"

        search_context_blocks = []
        for item in context["search_context"]:
            result_lines = []
            for r in item["results"]:
                location = r["file_path"] or "unknown_file"
                if r["start_line"] and r["end_line"]:
                    location += f":{r['start_line']}-{r['end_line']}"
                result_lines.append(f"  - {location} | score={r['score']:.4f}")

            block = f"Question: {item['question']}\n" + "\n".join(result_lines)
            search_context_blocks.append(block)

        search_context_text = "\n\n".join(search_context_blocks) if search_context_blocks else "None"

        return (
            f"Repository URL: {repository.repo_url}\n"
            f"Default Branch: {repository.default_branch}\n"
            f"Languages: {', '.join(context['languages']) if context['languages'] else 'Unknown'}\n"
            f"Total Indexed Files: {context['file_count']}\n\n"
            f"Important Files:\n{important_files_lines}\n\n"
            f"Hotspots:\n{hotspot_lines}\n\n"
            f"Semantic Hints:\n{search_context_text}\n\n"
            "Generate a markdown document with these exact sections:\n"
            "1. # Repository Onboarding Guide\n"
            "2. ## Quick Summary\n"
            "3. ## Likely Architecture Shape\n"
            "4. ## Where to Start Reading\n"
            "5. ## Likely Entrypoints\n"
            "6. ## Important Config / Build Files\n"
            "7. ## Risky / High-Attention Areas\n"
            "8. ## Suggested First-Day Reading Order\n"
            "9. ## Questions a New Engineer Should Ask\n"
            "10. ## Evidence (list key files)\n"
        )

    def _generate_deterministic_markdown(self, repository: Repository, context: dict) -> str:
        lines = []

        lines.append("# Repository Onboarding Guide")
        lines.append("")
        lines.append("## Quick Summary")
        lines.append("")
        lines.append(f"- Repository: `{repository.repo_url}`")
        lines.append(f"- Default branch: `{repository.default_branch}`")
        lines.append(f"- Indexed files: **{context['file_count']}**")
        lines.append(
            f"- Detected languages: **{', '.join(context['languages']) if context['languages'] else 'Unknown'}**"
        )
        lines.append("")

        lines.append("## Likely Architecture Shape")
        lines.append("")
        if context["languages"]:
            lines.append(
                f"This repository appears to be primarily built with **{', '.join(context['languages'])}**."
            )
        else:
            lines.append("Language detection is incomplete, so architecture inference is limited.")

        if context["entrypoints"]:
            lines.append(
                "There are likely centralized entrypoints or orchestration files, suggesting a structured application flow."
            )
        else:
            lines.append(
                "No strong entrypoint candidates were detected, so the project may be library-oriented or distributed."
            )
        lines.append("")

        lines.append("## Where to Start Reading")
        lines.append("")
        if context["important_files"]:
            for f in context["important_files"][:8]:
                lines.append(
                    f"- `{f['path']}` "
                    f"(kind={f['file_kind']}, lang={f['language']}, symbols={f['symbol_count']}, "
                    f"in={f['inbound_dependencies']}, out={f['outbound_dependencies']})"
                )
        else:
            lines.append("- No important files detected yet.")
        lines.append("")

        lines.append("## Likely Entrypoints")
        lines.append("")
        if context["entrypoints"]:
            for f in context["entrypoints"]:
                lines.append(f"- `{f['path']}`")
        else:
            lines.append("- No strong entrypoint candidates found.")
        lines.append("")

        lines.append("## Important Config / Build Files")
        lines.append("")
        if context["config_files"]:
            for f in context["config_files"]:
                lines.append(f"- `{f['path']}`")
        else:
            lines.append("- No major config/build files detected in top-ranked files.")
        lines.append("")

        lines.append("## Risky / High-Attention Areas")
        lines.append("")
        if context["hotspots"]:
            for h in context["hotspots"]:
                lines.append(
                    f"- `{h['path']}` → risk={h['risk_score']} ({h['risk_level']}) | "
                    f"symbols={h['symbol_count']} | inbound={h['inbound_dependencies']} | outbound={h['outbound_dependencies']}"
                )
        else:
            lines.append("- No hotspot data available.")
        lines.append("")

        lines.append("## Suggested First-Day Reading Order")
        lines.append("")
        reading_order = []
        reading_order.extend(context["entrypoints"][:3])
        reading_order.extend([f for f in context["config_files"][:3] if f not in reading_order])
        reading_order.extend([f for f in context["source_files"][:5] if f not in reading_order])

        if reading_order:
            for idx, f in enumerate(reading_order, start=1):
                lines.append(f"{idx}. `{f['path']}`")
        else:
            lines.append("1. Start with top-level README and key source files once available.")
        lines.append("")

        lines.append("## Questions a New Engineer Should Ask")
        lines.append("")
        lines.append("- Which file is the true runtime entrypoint in production?")
        lines.append("- Which modules are most critical to request flow / business logic?")
        lines.append("- Which files are considered risky to modify?")
        lines.append("- Are there hidden generated/vendor files excluded from this analysis?")
        lines.append("- What test suites cover the most important code paths?")
        lines.append("")

        lines.append("## Evidence")
        lines.append("")
        for f in context["important_files"][:10]:
            lines.append(f"- `{f['path']}`")

        lines.append("")
        return "\n".join(lines)

    def _is_likely_entrypoint(self, path: str) -> bool:
        normalized = path.lower()

        entrypoint_keywords = [
            "main.py",
            "__main__.py",
            "app.py",
            "server.py",
            "index.js",
            "index.ts",
            "main.ts",
            "main.js",
            "cli.py",
            "manage.py",
            "run.py",
            "wsgi.py",
            "asgi.py",
        ]

        if any(normalized.endswith(keyword) for keyword in entrypoint_keywords):
            return True

        if "/cmd/" in normalized or "/bin/" in normalized:
            return True

        return False
