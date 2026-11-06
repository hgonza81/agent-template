from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from agent_template_api.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "identity_issuer",
            "identity_subject",
            name="uq_subscriptions_identity_issuer_subject",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    identity_issuer: Mapped[str] = mapped_column(String, nullable=False)
    identity_subject: Mapped[str] = mapped_column(String, nullable=False)
    email_snapshot: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    foundry_thread_id: Mapped[str | None] = mapped_column(String, nullable=True)
