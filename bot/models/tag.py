from sqlalchemy import ForeignKey, String, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database import Base


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id: Mapped[str] = mapped_column(String(256), nullable=False)
    order: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    media_type: Mapped[str] = mapped_column(String(10), default="photo", nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="photos")

    def __repr__(self) -> str:
        return f"<Photo id={self.id} user_id={self.user_id} order={self.order} media_type={self.media_type!r}>"

class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    user_tags: Mapped[list["UserTag"]] = relationship("UserTag", back_populates="tag")

    def __repr__(self) -> str:
        return f"<Tag id={self.id} name={self.name!r}>"


class UserTag(Base):
    __tablename__ = "user_tags"
    __table_args__ = (UniqueConstraint("user_id", "tag_id", name="uq_user_tag"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)

    user: Mapped["User"] = relationship("User", back_populates="tags")  # type: ignore[name-defined]
    tag: Mapped[Tag] = relationship("Tag", back_populates="user_tags")
