from datetime import datetime, date
from typing import Optional
from sqlalchemy import ForeignKey, String, Boolean, Integer, Date, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from bot.database import Base

class EventCategory(Base):
    __tablename__ = "event_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    emoji: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("event_categories.id"), nullable=False)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # relationships
    creator: Mapped["User"] = relationship("User", foreign_keys=[creator_id])
    category: Mapped["EventCategory"] = relationship("EventCategory")