from aiogram import Dispatcher

from bot.handlers.registration import router as registration_router
from bot.handlers.browse import router as browse_router
from bot.handlers.profile import router as profile_router
from bot.handlers.admin import router as admin_router
from bot.handlers.payment import router as payment_router

def register_all_handlers(dp: Dispatcher) -> None:
    dp.include_router(admin_router)
    dp.include_router(registration_router)
    dp.include_router(profile_router)
    dp.include_router(browse_router)
    dp.include_router(payment_router)