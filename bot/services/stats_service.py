from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models import User, Like, Viewed, UserTag


class StatsService:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_stats(self, user: User) -> dict:
        # Сколько лайков получила анкета
        likes_received = (await self.session.execute(
            select(func.count()).where(Like.to_id == user.id)
        )).scalar_one()

        # Сколько лайков поставил сам
        likes_sent = (await self.session.execute(
            select(func.count()).where(Like.from_id == user.id)
        )).scalar_one()

        # Сколько чужих анкет просмотрел
        profiles_viewed = (await self.session.execute(
            select(func.count()).where(Viewed.viewer_id == user.id)
        )).scalar_one()

        # Место в рейтинге — считаем сколько людей получили больше лайков чем ты
        my_likes_count = likes_received

        users_ahead = (await self.session.execute(
            select(func.count()).select_from(
                select(func.count(Like.id).label("cnt"))
                .where(Like.to_id != user.id)
                .join(User, User.id == Like.to_id)
                .where(User.is_active.is_(True), User.is_banned.is_(False))
                .group_by(Like.to_id)
                .having(func.count(Like.id) > my_likes_count)
                .subquery()
            )
        )).scalar_one_or_none() or 0

        rank = users_ahead + 1

        return {
            "likes_received": likes_received,
            "likes_sent": likes_sent,
            "profiles_viewed": profiles_viewed,
            "views_count": user.views_count,
            "rank": rank,
        }

    async def get_top5(self) -> list:
        # Сначала получаем топ 5 user_id по лайкам
        result = await self.session.execute(
            select(User.id, func.count(Like.id).label("likes_count"))
            .join(Like, Like.to_id == User.id, isouter=True)
            .where(User.is_active.is_(True), User.is_banned.is_(False))
            .group_by(User.id)
            .order_by(func.count(Like.id).desc())
            .limit(5)
        )
        rows = result.all()  # [(user_id, likes_count), ...]

        if not rows:
            return []

        # Загружаем пользователей с фото и тегами отдельно
        user_ids = [r[0] for r in rows]
        likes_map = {r[0]: r[1] for r in rows}

        users_result = await self.session.execute(
            select(User)
            .where(User.id.in_(user_ids))
            .options(
                selectinload(User.photos),
                selectinload(User.tags).selectinload(UserTag.tag),
            )
        )
        users = {u.id: u for u in users_result.scalars().all()}

        # Возвращаем в правильном порядке (по убыванию лайков)
        return [(users[uid], likes_map[uid]) for uid in user_ids if uid in users]

    def format_stats(self, stats: dict) -> str:
        return (
            "📊 <b>Твоя статистика</b>\n\n"
            f"🏆 Место в рейтинге: <b>#{stats['rank']}</b>\n\n"
            f"👁 Просмотров твоей анкеты: <b>{stats['views_count']}</b>\n"
            f"❤️ Лайков получено: <b>{stats['likes_received']}</b>\n\n"
            f"🔍 Анкет просмотрено тобой: <b>{stats['profiles_viewed']}</b>\n"
            f"👍 Лайков поставлено: <b>{stats['likes_sent']}</b>\n"
        )