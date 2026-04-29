from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Boolean, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database import Base


class Like(Base):
    """
    Хранит все оценки: обычный лайк, суперлайк, лайк с сообщением.

    type:
        'like'    — обычный лайк
        'super'   — суперлайк
        'message' — лайк + сообщение (поле message заполнено)

    is_mutual:
        True  — получатель лайкнул в ответ (матч состоялся)
        False — ожидание ответа
    """
    __tablename__ = "likes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)   # like / super / message
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_mutual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    is_viewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    from_user: Mapped["User"] = relationship("User", foreign_keys=[from_id])  # type: ignore[name-defined]
    to_user: Mapped["User"] = relationship("User", foreign_keys=[to_id])       # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Like id={self.id} from={self.from_id} to={self.to_id} type={self.type!r}>"
