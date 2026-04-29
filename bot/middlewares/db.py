from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.database import AsyncSessionFactory


class DbSessionMiddleware(BaseMiddleware):
    """
    Создаёт сессию БД на каждый апдейт и кладёт её в data['session'].
    Хэндлеры получают сессию через аргумент session: AsyncSession.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with AsyncSessionFactory() as session:
            data["session"] = session
            return await handler(event, data)
