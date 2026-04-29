from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import BigInteger, String, Boolean, SmallInteger, Date, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Основные данные анкеты
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    age: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    gender: Mapped[str] = mapped_column(String(1), nullable=False)   # 'M' или 'F'
    height: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    goal: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # night/relationship/friendship
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Статус анкеты
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Подписка
    has_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    premium_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Счётчики лимитов (сбрасываются каждый день)
    super_like_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    msg_like_count: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    msg_like_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Буст анкеты
    views_count: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    is_boosted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    boost_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # После created_at добавь:
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # И поля для отслеживания отправленных напоминаний (чтобы не спамить)
    notified_at_24h: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notified_at_72h: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notified_at_168h: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notified_at_336h: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notified_at_720h: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    photos: Mapped[List["Photo"]] = relationship(
        "Photo", back_populates="user", order_by="Photo.order", cascade="all, delete-orphan"
    )
    tags: Mapped[List["UserTag"]] = relationship(
        "UserTag", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} tg_id={self.tg_id} name={self.name!r}>"
