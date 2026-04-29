from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.services.payment import create_payment
from bot.keyboards import main_menu_kb
from bot.utils.formatters import format_subscription_info

router = Router()


# 1. Показываем описание подписки при нажатии на кнопку "⭐ Подписка"
@router.message(F.text == "⭐ Подписка")
async def show_subscription_info(message: Message):
    """Показывает красивое описание подписки с кнопкой оплаты"""
    text = format_subscription_info()

    # Кнопка для перехода к оплате
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оформить за 39 ₽/мес", callback_data="subscription:pay")]
    ])

    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery, session: AsyncSession):
    """Проверяет статус последнего платежа"""
    # Здесь нужно хранить payment_id в state или metadata
    # Пока временно
    await callback.answer("После оплаты подписка активируется автоматически в течение 1 минуты", show_alert=True)

@router.callback_query(F.data == "profile:subscription")
async def show_subscription_info(callback: CallbackQuery):
    text = format_subscription_info()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оформить за 39 ₽/мес", callback_data="subscription:pay")]
    ])

    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

# 2. Обрабатываем нажатие на кнопку оплаты
@router.callback_query(F.data == "subscription:pay")
async def handle_payment(callback: CallbackQuery, session: AsyncSession):
    """Создаёт платёж и отправляет ссылку"""
    user_id = callback.from_user.id

    # Отвечаем на callback, чтобы убрать "часики"
    await callback.answer()

    # Редактируем сообщение, убираем кнопку
    await callback.message.edit_reply_markup(reply_markup=None)

    payment_url = await create_payment(
        amount=settings.SUBSCRIPTION_PRICE,
        description="Подписка на 30 дней",
        user_tg_id=user_id
    )

    if payment_url:
        await callback.message.answer(
            f"💰 <b>Оплата подписки {settings.SUBSCRIPTION_PRICE}₽</b>\n\n"
            f"💳 <a href='{payment_url}'>Нажмите для оплаты</a>\n\n"
            f"⚡ После оплаты подписка активируется автоматически.\n\n"
            f"🔁 Вернитесь в бот после оплаты, чтобы проверить статус: /start",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
    else:
        await callback.message.answer(
            "❌ Ошибка при создании платежа. Попробуйте позже.",
            reply_markup=main_menu_kb(),
        )