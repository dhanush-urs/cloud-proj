from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("delivery_id", name="uq_webhook_events_delivery_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="github")
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    delivery_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    repository_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, index=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)

    action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="received")

    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
