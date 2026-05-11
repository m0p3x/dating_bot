import asyncio
from aiogram import Bot
from bot.config import settings
from bot.database import AsyncSessionFactory
from bot.models import User
from sqlalchemy import select

async def clean_blocked():
    bot = Bot(token=settings.BOT_TOKEN)
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        deleted = 0
        for user in users:
            try:
                await bot.send_chat_action(chat_id=user.tg_id, action="typing")
            except Exception as e:
                if "blocked" in str(e).lower():
                    await session.delete(user)
                    deleted += 1
                    print(f"Удалён: {user.name} (tg_id={user.tg_id})")
        await session.commit()
        print(f"✅ Удалено {deleted} пользователей")

asyncio.run(clean_blocked())