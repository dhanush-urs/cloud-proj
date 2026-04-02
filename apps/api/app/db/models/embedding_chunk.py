from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmbeddingChunk(Base):
    __tablename__ = "embedding_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    repository_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    file_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    chunk_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)

    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding_vector: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string for now

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
