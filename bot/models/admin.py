from datetime import datetime

from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from bot.database import Base


class Admin(Base):
    """
    На старте — один admin, tg_id берётся из ADMIN_IDS в .env.
    Таблица заготовлена для расширения без переписывания логики.
    """
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Admin id={self.id} tg_id={self.tg_id}>"
