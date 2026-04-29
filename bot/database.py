from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from bot.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,          # True — выводить SQL в лог (удобно при отладке)
    pool_size=10,
    max_overflow=20,
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    """Dependency — используется в middleware для внедрения сессии в хэндлеры."""
    async with AsyncSessionFactory() as session:
        yield session
