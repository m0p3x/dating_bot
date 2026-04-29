from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database import Base


class Viewed(Base):
    """
    Фиксирует, что viewer_id просмотрел анкету viewed_id.
    Анкета снова появляется в выдаче через VIEWED_TTL_HOURS часов (24ч по умолчанию).
    """
    __tablename__ = "viewed"
    __table_args__ = (UniqueConstraint("viewer_id", "viewed_id", name="uq_viewer_viewed"),)

    viewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    viewed_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Report(Base):
    """
    Жалоба от одного пользователя на другого.

    reason:
        'spam'      — реклама / спам
        'offensive' — оскорбительный контент
        'fake'      — фейковый профиль
        'other'     — другое (поле comment заполняется)

    status:
        'pending'   — ожидает рассмотрения
        'resolved'  — рассмотрена, приняты меры
        'dismissed' — отклонена (нарушений не найдено)
    """
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    to_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    reported_user: Mapped["User"] = relationship("User", foreign_keys=[to_id])  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Report id={self.id} from={self.from_id} to={self.to_id} reason={self.reason!r} status={self.status!r}>"
