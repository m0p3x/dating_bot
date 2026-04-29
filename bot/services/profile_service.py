from typing import Optional, List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models import User, Photo, Tag, UserTag


class ProfileService:

    def __init__(self, session: AsyncSession):
        self.session = session

    # ──────────────────────────────────────────────
    # Получение пользователя
    # ──────────────────────────────────────────────

    async def get_by_tg_id(self, tg_id: int) -> Optional[User]:
        """Загружает пользователя вместе с фото и тегами."""
        result = await self.session.execute(
            select(User)
            .where(User.tg_id == tg_id)
            .options(
                selectinload(User.photos),
                selectinload(User.tags).selectinload(UserTag.tag),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.photos),
                selectinload(User.tags).selectinload(UserTag.tag),
            )
        )
        return result.scalar_one_or_none()

    async def exists(self, tg_id: int) -> bool:
        result = await self.session.execute(
            select(User.id).where(User.tg_id == tg_id)
        )
        return result.scalar_one_or_none() is not None

    # ──────────────────────────────────────────────
    # Создание и обновление
    # ──────────────────────────────────────────────

    async def create(
        self,
        tg_id: int,
        username: Optional[str],
        name: str,
        age: int,
        gender: str,
        height: Optional[int] = None,
        city: Optional[str] = None,
        goal: Optional[str] = None,
        bio: Optional[str] = None,
    ) -> User:
        user = User(
            tg_id=tg_id,
            username=username,
            name=name,
            age=age,
            gender=gender,
            height=height,
            city=city,
            goal=goal,
            bio=bio,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update_field(self, tg_id: int, **kwargs) -> None:
        """Обновляет произвольные поля пользователя по tg_id."""
        user = await self.get_by_tg_id(tg_id)
        if user is None:
            return
        for field, value in kwargs.items():
            setattr(user, field, value)
        await self.session.commit()

    # ──────────────────────────────────────────────
    # Фото
    # ──────────────────────────────────────────────

    async def add_photo(self, user_id: int, file_id: str, order: int = 0, media_type: str = "photo"):
        photo = Photo(user_id=user_id, file_id=file_id, order=order, media_type=media_type)
        self.session.add(photo)
        await self.session.commit()

    async def delete_photos(self, user_id: int) -> None:
        await self.session.execute(
            delete(Photo).where(Photo.user_id == user_id)
        )
        await self.session.commit()

    # ──────────────────────────────────────────────
    # Теги (увлечения)
    # ──────────────────────────────────────────────

    async def update_activity(self, tg_id: int) -> None:
        """Обновляет время последней активности пользователя"""
        from datetime import datetime, timezone
        user = await self.get_by_tg_id(tg_id)
        if user:
            user.last_activity = datetime.now(timezone.utc)
            await self.session.commit()

    async def get_or_create_tag(self, name: str) -> Tag:
        result = await self.session.execute(
            select(Tag).where(Tag.name == name)
        )
        tag = result.scalar_one_or_none()
        if tag is None:
            tag = Tag(name=name)
            self.session.add(tag)
            await self.session.flush()
        return tag

    async def set_tags(self, user_id: int, tag_names: List[str]) -> None:
        """Полностью заменяет теги пользователя."""
        # Удаляем старые
        await self.session.execute(
            delete(UserTag).where(UserTag.user_id == user_id)
        )
        # Создаём новые
        for name in tag_names:
            tag = await self.get_or_create_tag(name)
            self.session.add(UserTag(user_id=user_id, tag_id=tag.id))
        await self.session.commit()

    # ──────────────────────────────────────────────
    # Статус анкеты
    # ──────────────────────────────────────────────

    async def deactivate(self, tg_id: int) -> None:
        await self.update_field(tg_id, is_active=False)

    async def activate(self, tg_id: int) -> None:
        await self.update_field(tg_id, is_active=True)

    async def delete_profile(self, tg_id: int) -> None:
        user = await self.get_by_tg_id(tg_id)
        if user:
            await self.session.delete(user)
            await self.session.commit()
