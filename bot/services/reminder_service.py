from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot

from bot.models import User


class ReminderService:
    # Интервалы в часах и соответствующие названия полей в БД
    REMINDERS = [
        (24, "notified_at_24h", "👋 Новые анкеты уже ждут тебя. Загляни в поиск 🔍"),
        (72, "notified_at_72h", "😔 По тебе скучают... Загляни в бот — возможно, тебя уже кто-то лайкнул!"),
        (168, "notified_at_168h", "💔 Не пропадай! У тебя могут быть новые лайки. Проверь ❤️ Кто меня лайкнул"),
        (336, "notified_at_336h", "Мы тебя очень ждем!!!"),
        (720, "notified_at_720h",
         "⚠️ Твой профиль будет скрыт через 3 дня, если не зайдёшь. Нажми /start, чтобы оставаться в поиске!"),
    ]

    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot

    async def check_and_notify(self):
        """Проверяет неактивных пользователей и отправляет напоминания"""
        now = datetime.now(timezone.utc)

        for hours, field_name, message in self.REMINDERS:
            cutoff = now - timedelta(hours=hours)

            query = select(User).where(
                User.last_activity <= cutoff,
                User.last_activity > cutoff - timedelta(hours=1),
                getattr(User, field_name) == False,
                User.is_active == True,
                User.is_banned == False,
            )

            result = await self.session.execute(query)
            users = result.scalars().all()

            for user in users:
                try:
                    await self.bot.send_message(
                        chat_id=user.tg_id,
                        text=message,
                        parse_mode="HTML",
                    )
                    setattr(user, field_name, True)
                    await self.session.commit()
                except Exception:
                    pass  # тихо игнорируем ошибки (бот не может писать пользователю)