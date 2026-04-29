from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.config import settings


class IsAdmin(BaseFilter):
    """
    Фильтр: True если tg_id отправителя есть в ADMIN_IDS.
    Работает как для Message, так и для CallbackQuery.
    """

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        if event.from_user is None:
            return False
        return event.from_user.id in settings.ADMIN_IDS
