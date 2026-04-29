from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str

    # Администраторы
    ADMIN_IDS: List[int] = []

    # Подписка
    SUBSCRIPTION_PRICE: int = 39
    SUBSCRIPTION_URL: str = "https://your-payment-page.com"

    # ЮKassa
    YOOKASSA_SHOP_ID: str = "1342309"
    YOOKASSA_SECRET_KEY: str = "live_FiImRfDslQnuB36tHQXz2jfdlDU1SP_HCf0moXn6OCo"
    YOOKASSA_RETURN_URL: str = "https://t.me/GAZznakomitsya_bot"

    # Лимиты
    MSG_LIKE_DAILY_LIMIT: int = 3
    SUPER_LIKE_DAILY_LIMIT: int = 1

    # Алгоритм поиска
    VIEWED_TTL_HOURS: int = 1
    HEIGHT_FILTER_RANGE: int = 5
    AGE_FILTER_RANGE: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()