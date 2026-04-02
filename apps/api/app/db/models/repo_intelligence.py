"""RepoIntelligence — persistent repo-wide memory artifact.

Built during parse time by RepoIntelligenceService and loaded at Ask Repo
query time as the primary intelligence layer for repo_summary questions.
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RepoIntelligence(Base):
    __tablename__ = "repo_intelligence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    repository_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        unique=True,  # one artifact per repo
    )

    # ── Language & Framework ───────────────────────────────────────────────
    primary_language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    frameworks: Mapped[str | None] = mapped_column(Text, nullable=True)          # JSON array
    build_tools: Mapped[str | None] = mapped_column(Text, nullable=True)          # JSON array
    test_frameworks: Mapped[str | None] = mapped_column(Text, nullable=True)      # JSON array

    # ── Structure ──────────────────────────────────────────────────────────
    top_level_dirs: Mapped[str | None] = mapped_column(Text, nullable=True)       # JSON array
    entrypoints: Mapped[str | None] = mapped_column(Text, nullable=True)          # JSON array of paths
    key_files: Mapped[str | None] = mapped_column(Text, nullable=True)            # JSON array of paths
    detected_services: Mapped[str | None] = mapped_column(Text, nullable=True)    # JSON array
    detected_apps: Mapped[str | None] = mapped_column(Text, nullable=True)        # JSON array

    # ── Backend / Frontend Split ───────────────────────────────────────────
    backend_paths: Mapped[str | None] = mapped_column(Text, nullable=True)        # JSON array
    frontend_paths: Mapped[str | None] = mapped_column(Text, nullable=True)       # JSON array

    # ── Domain Summaries ──────────────────────────────────────────────────
    api_routes_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    db_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    deployment_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Narrative Summaries ───────────────────────────────────────────────
    repo_summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    architecture_summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    module_map_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Stats ─────────────────────────────────────────────────────────────
    total_source_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_symbols: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── Versioning ────────────────────────────────────────────────────────
    ingestion_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    repository = relationship("Repository", back_populates="intelligence")
