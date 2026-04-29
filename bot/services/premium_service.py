from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import User
from bot.services.profile_service import ProfileService


class PremiumService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self._profile = ProfileService(session)

    async def grant(self, tg_id: int, days: int = 30) -> None:
        """Выдаёт подписку пользователю на указанное количество дней."""
        user = await self._profile.get_by_tg_id(tg_id)
        if user is None:
            return
        now = datetime.now(timezone.utc)
        # Если подписка ещё активна — продлеваем, иначе стартуем с сейчас
        base = user.premium_until if (user.premium_until and user.premium_until > now) else now
        user.has_premium = True
        user.premium_until = base + timedelta(days=days)
        await self.session.commit()

    async def revoke(self, tg_id: int) -> None:
        """Снимает подписку."""
        await self._profile.update_field(tg_id, has_premium=False, premium_until=None)

    async def check_and_expire(self, user: User) -> bool:
        """
        Проверяет, не истекла ли подписка.
        Если истекла — обнуляет флаг. Возвращает актуальное значение has_premium.
        """
        if not user.has_premium:
            return False
        if user.premium_until and user.premium_until < datetime.now(timezone.utc):
            user.has_premium = False
            user.premium_until = None
            await self.session.commit()
            return False
        return True

    async def grant_boost(self, tg_id: int, hours: int = 24) -> bool:
        """Ставит буст анкеты на hours часов. Только для премиум-пользователей."""
        user = await self._profile.get_by_tg_id(tg_id)
        if user is None or not user.has_premium:
            return False
        user.is_boosted = True
        user.boost_until = datetime.now(timezone.utc) + timedelta(hours=hours)
        await self.session.commit()
        return True

    # premium_service.py
    async def grant_free_trial(self, user_db_id: int, hours: int = 24) -> bool:
        user = await self._profile.get_by_id(user_db_id)
        if user is None:
            return False
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        base = user.premium_until if (user.premium_until and user.premium_until > now) else now
        user.has_premium = True
        user.premium_until = base + timedelta(hours=hours)
        await self.session.commit()
        return True

    async def activate_subscription(self, tg_id: int, days: int = 30) -> None:
        """Активирует подписку после успешной оплаты"""
        await self.grant(tg_id, days=days)
    
    async def check_and_expire_boost(self, user: User) -> None:
        """Снимает буст если время истекло."""
        if user.is_boosted and user.boost_until:
            if user.boost_until < datetime.now(timezone.utc):
                user.is_boosted = False
                user.boost_until = None
                await self.session.commit()
