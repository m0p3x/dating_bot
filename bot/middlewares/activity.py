from datetime import datetime, timezone
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.services.profile_service import ProfileService


class ActivityMiddleware(BaseMiddleware):
    """Обновляет время последней активности пользователя при любом действии"""

    async def __call__(self, handler, event, data):
        # Получаем сессию из данных
        session: AsyncSession = data.get("session")

        if session:
            # Определяем ID пользователя из разных типов событий
            user_id = None
            if hasattr(event, "from_user") and event.from_user:
                user_id = event.from_user.id
            elif hasattr(event, "message") and event.message and event.message.from_user:
                user_id = event.message.from_user.id
            elif hasattr(event, "callback_query") and event.callback_query and event.callback_query.from_user:
                user_id = event.callback_query.from_user.id

            if user_id:
                svc = ProfileService(session)
                await svc.update_activity(user_id)

        return await handler(event, data)