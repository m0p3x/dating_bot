from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import User


class BanCheckMiddleware(BaseMiddleware):
    """
    Проверяет, не забанен ли пользователь.
    Если забанен — молча игнорируем апдейт (не отвечаем).
    Запускается после DbSessionMiddleware, поэтому session уже в data.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Определяем tg_id из разных типов апдейтов
        tg_id: int | None = None
        if isinstance(event, Message) and event.from_user:
            tg_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            tg_id = event.from_user.id

        if tg_id is None:
            return await handler(event, data)

        session: AsyncSession = data.get("session")
        if session is None:
            return await handler(event, data)

        result = await session.execute(
            select(User.is_banned).where(User.tg_id == tg_id)
        )
        row = result.scalar_one_or_none()

        # Пользователь не зарегистрирован — пропускаем (регистрация его подхватит)
        if row is None:
            return await handler(event, data)

        if row is True:
            # Забанен — ничего не делаем
            return None

        return await handler(event, data)
