from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.services.payment import create_payment
from bot.keyboards import main_menu_kb, subscription_plans_kb
from bot.utils.formatters import format_subscription_info
from bot.services.profile_service import ProfileService

router = Router()


@router.message(F.text == "⭐ Подписка")
async def show_subscription_plans(message: Message, session: AsyncSession):
    """Показывает варианты подписки с информацией о текущей"""
    svc = ProfileService(session)
    user = await svc.get_by_tg_id(message.from_user.id)
    text = format_subscription_info(user)
    await message.answer(text, parse_mode="HTML", reply_markup=subscription_plans_kb())


@router.callback_query(F.data == "profile:subscription")
async def show_subscription_plans_callback(callback: CallbackQuery, session: AsyncSession):
    """Показывает варианты подписки (из профиля)"""
    svc = ProfileService(session)
    user = await svc.get_by_tg_id(callback.from_user.id)
    text = format_subscription_info(user)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=subscription_plans_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("sub_plan:"))
async def handle_subscription_plan(callback: CallbackQuery, session: AsyncSession):
    """Обработка выбора плана подписки"""
    months = int(callback.data.split(":")[1])

    # Определяем цену в зависимости от срока
    if months == 1:
        amount = settings.SUBSCRIPTION_PRICE_1_MONTH
    elif months == 3:
        amount = settings.SUBSCRIPTION_PRICE_3_MONTHS
    elif months == 6:
        amount = settings.SUBSCRIPTION_PRICE_6_MONTHS
    else:
        amount = settings.SUBSCRIPTION_PRICE_12_MONTHS

    user_id = callback.from_user.id

    # Отвечаем на callback, чтобы убрать "часики"
    await callback.answer()

    # Редактируем сообщение, убираем кнопки
    await callback.message.edit_reply_markup(reply_markup=None)

    payment_url = await create_payment(
        amount=amount,
        description=f"Подписка на {months} месяц(ев)",
        user_tg_id=user_id,
        months=months
    )

    if payment_url:
        await callback.message.answer(
            f"💰 <b>Оплата подписки на {months} месяц(ев) — {amount}₽</b>\n\n"
            f"💳 <a href='{payment_url}'>Нажмите для оплаты</a>\n\n"
            f"⚡ После оплаты подписка активируется автоматически.\n\n"
            f"🔁 Вернитесь в бот после оплаты и нажмите /start для обновления статуса",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
    else:
        await callback.message.answer(
            "❌ Ошибка при создании платежа. Попробуйте позже.",
            reply_markup=main_menu_kb(),
        )


@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery):
    await callback.answer("После оплаты подписка активируется автоматически в течение 1 минуты", show_alert=True)