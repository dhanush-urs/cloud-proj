from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    repo_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    provider: Mapped[str] = mapped_column(String(50), default="github", nullable=False)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)
    primary_language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detected_languages: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_frameworks: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_symbols: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    branches = relationship("Branch", back_populates="repository", cascade="all, delete-orphan")
    files = relationship("File", back_populates="repository", cascade="all, delete-orphan")
    jobs = relationship("RepoJob", back_populates="repository", cascade="all, delete-orphan")
    snapshots = relationship("RepoSnapshot", back_populates="repository", cascade="all, delete-orphan")
    intelligence = relationship("RepoIntelligence", back_populates="repository", uselist=False, cascade="all, delete-orphan")
