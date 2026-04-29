from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database import Base


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Кто пригласил
    referrer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Кого пригласили
    referred_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)

    # Был ли активирован бонус
    bonus_granted: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    referrer: Mapped["User"] = relationship("User", foreign_keys=[referrer_id])
    referred: Mapped["User"] = relationship("User", foreign_keys=[referred_id])