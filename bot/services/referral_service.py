import base64
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import User, Referral
from bot.services.premium_service import PremiumService


class ReferralService:
    REFERRAL_BONUS_HOURS = 24  # 24 часа подписки за приглашение

    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_referral_link(self, user_id: int) -> str:
        """Генерирует реферальную ссылку"""
        code = base64.urlsafe_b64encode(str(user_id).encode()).decode()
        return f"https://t.me/GAZznakomitsya_bot?start=ref_{code}"

    async def decode_referral_code(self, code: str) -> int | None:
        """Декодирует реферальный код в user_id"""
        if not code or not code.startswith("ref_"):
            return None
        try:
            encoded = code.replace("ref_", "")
            user_id = int(base64.urlsafe_b64decode(encoded.encode()).decode())
            return user_id
        except Exception:
            return None

    async def process_referral(self, referred_user_id: int, referrer_code: str) -> bool:
        """
        Обрабатывает переход по реферальной ссылке.
        Возвращает True, если реферал успешно зарегистрирован.
        """
        referrer_id = await self.decode_referral_code(referrer_code)
        if not referrer_id:
            return False

        # Нельзя реферить самого себя
        if referrer_id == referred_user_id:
            return False

        # Проверяем, не был ли уже этот пользователь приглашён
        existing = await self.session.execute(
            select(Referral).where(Referral.referred_id == referred_user_id)
        )
        if existing.scalar_one_or_none():
            return False

        # Создаём запись о реферале
        referral = Referral(
            referrer_id=referrer_id,
            referred_id=referred_user_id,
        )
        self.session.add(referral)
        await self.session.commit()

        return True

    async def grant_referral_bonus(self, referred_user_id: int, bot=None) -> bool:
        """
        Начисляет бонус пригласившему после полной регистрации реферала.
        """
        # Находим реферальную запись
        result = await self.session.execute(
            select(Referral)
            .where(Referral.referred_id == referred_user_id)
            .where(Referral.bonus_granted == False)
        )
        referral = result.scalar_one_or_none()

        if not referral:
            return False

        # Получаем пользователя, который зарегистрировался
        result_user = await self.session.execute(
            select(User).where(User.id == referred_user_id)
        )
        new_user = result_user.scalar_one_or_none()

        # Начисляем бонус пригласившему
        premium_svc = PremiumService(self.session)
        success = await premium_svc.grant_free_trial(referral.referrer_id, hours=self.REFERRAL_BONUS_HOURS)

        if success:
            referral.bonus_granted = True
            await self.session.commit()

            # Уведомляем пригласившего
            result_referrer = await self.session.execute(
                select(User).where(User.id == referral.referrer_id)
            )
            referrer = result_referrer.scalar_one_or_none()
            if referrer and bot and new_user:
                try:
                    await bot.send_message(
                        chat_id=referrer.tg_id,
                        text=f"🎉 <b>Ваш друг {new_user.name} завершил регистрацию!</b>\n\n"
                             f"Вы получили <b>{self.REFERRAL_BONUS_HOURS} часа</b> подписки бесплатно! ⭐\n\n"
                             f"Продолжайте приглашать друзей и получайте ещё больше бонусов!",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
            return True

        return False

    async def get_referral_stats(self, user_id: int) -> dict:
        """Получает статистику рефералов пользователя"""
        # Количество приглашённых
        total_result = await self.session.execute(
            select(func.count(Referral.id))
            .where(Referral.referrer_id == user_id)
        )
        total = total_result.scalar_one() or 0

        # Количество активированных (получивших бонус)
        activated_result = await self.session.execute(
            select(func.count(Referral.id))
            .where(Referral.referrer_id == user_id)
            .where(Referral.bonus_granted == True)
        )
        activated = activated_result.scalar_one() or 0

        return {
            "total": total,
            "activated": activated,
            "bonus_hours": self.REFERRAL_BONUS_HOURS,
        }