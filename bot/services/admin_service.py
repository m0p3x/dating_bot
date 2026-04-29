from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models import User, Like, UserTag
from bot.services.profile_service import ProfileService
from bot.services.premium_service import PremiumService


class AdminService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self._profile = ProfileService(session)
        self._premium = PremiumService(session)

    # ──────────────────────────────────────────────
    # Поиск пользователя
    # ──────────────────────────────────────────────

    async def find_user(self, query: str) -> Optional[User]:
        """Ищет по @username или tg_id."""
        query = query.strip().lstrip("@")
        result = None
        # Пробуем tg_id
        if query.isdigit():
            result = await self.session.execute(
                select(User)
                .where(User.tg_id == int(query))
                .options(
                    selectinload(User.photos),
                    selectinload(User.tags).selectinload(UserTag.tag),
                )
            )
            user = result.scalar_one_or_none()
            if user:
                return user
        # Иначе по username
        result = await self.session.execute(
            select(User)
            .where(User.username == query)
            .options(
                selectinload(User.photos),
                selectinload(User.tags).selectinload(UserTag.tag),
            )
        )
        return result.scalar_one_or_none()

    # ──────────────────────────────────────────────
    # Бан / разбан
    # ──────────────────────────────────────────────

    async def ban(self, user_id_db: int) -> None:
        result = await self.session.execute(select(User).where(User.id == user_id_db))
        user = result.scalar_one_or_none()
        if user:
            user.is_banned = True
            user.is_active = False
            await self.session.commit()

    async def unban(self, user_id_db: int) -> None:
        result = await self.session.execute(select(User).where(User.id == user_id_db))
        user = result.scalar_one_or_none()
        if user:
            user.is_banned = False
            user.is_active = True
            await self.session.commit()

    async def delete_profile(self, user_id_db: int) -> None:
        result = await self.session.execute(select(User).where(User.id == user_id_db))
        user = result.scalar_one_or_none()
        if user:
            await self.session.delete(user)
            await self.session.commit()

    # ──────────────────────────────────────────────
    # Подписка
    # ──────────────────────────────────────────────

    async def give_premium(self, tg_id: int) -> None:
        await self._premium.grant(tg_id, days=30)

    async def remove_premium(self, tg_id: int) -> None:
        await self._premium.revoke(tg_id)

    # ──────────────────────────────────────────────
    # Статистика
    # ──────────────────────────────────────────────

    async def get_stats(self) -> dict:
        now = datetime.now(timezone.utc)

        total = (await self.session.execute(
            select(func.count()).select_from(User)
        )).scalar_one()

        new_today = (await self.session.execute(
            select(func.count()).where(User.created_at >= now - timedelta(days=1))
        )).scalar_one()

        new_week = (await self.session.execute(
            select(func.count()).where(User.created_at >= now - timedelta(days=7))
        )).scalar_one()

        new_month = (await self.session.execute(
            select(func.count()).where(User.created_at >= now - timedelta(days=30))
        )).scalar_one()

        premium_count = (await self.session.execute(
            select(func.count()).where(User.has_premium.is_(True))
        )).scalar_one()

        matches = (await self.session.execute(
            select(func.count()).where(Like.is_mutual.is_(True))
        )).scalar_one()

        return {
            "total": total,
            "new_today": new_today,
            "new_week": new_week,
            "new_month": new_month,
            "premium": premium_count,
            "matches": matches,
        }

    def format_stats(self, stats: dict) -> str:
        return (
            "📊 <b>Статистика бота</b>\n\n"
            f"👥 Всего пользователей: <b>{stats['total']}</b>\n"
            f"🆕 Новые за сегодня: <b>{stats['new_today']}</b>\n"
            f"📅 Новые за неделю: <b>{stats['new_week']}</b>\n"
            f"🗓 Новые за месяц: <b>{stats['new_month']}</b>\n\n"
            f"⭐ Премиум-подписчиков: <b>{stats['premium']}</b>\n"
            f"💑 Всего матчей: <b>{stats['matches']}</b>\n"
        )
