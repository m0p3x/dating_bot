from datetime import datetime, date
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.states import FindCompany
from bot.keyboards import (
    company_mode_kb, company_categories_kb, company_confirm_kb,
    company_event_kb, company_my_event_kb, main_menu_kb
)
from bot.services.profile_service import ProfileService
from bot.services.event_service import EventService

router = Router()

# ---------- Переключение режима ----------
@router.message(F.text == "👥 Найти компанию")
async def enter_company_mode(message: Message, state: FSMContext, session: AsyncSession):
    svc = ProfileService(session)
    user = await svc.get_by_tg_id(message.from_user.id)
    if not user.city:
        await message.answer("❌ Укажите город в профиле, чтобы использовать этот режим.")
        return
    await state.set_state(FindCompany.browsing_categories)
    await message.answer("👥 Режим «Найти компанию»\n\n📌 Создайте встречу или найдите существующую.", reply_markup=company_mode_kb())

@router.message(F.text == "🔙 Выйти из режима")
async def exit_company_mode(message: Message, state: FSMContext):
    await state.set_state(None)
    await message.answer("Вы вернулись в режим знакомств.", reply_markup=main_menu_kb())

# ---------- Создание встречи ----------
@router.message(FindCompany.browsing_categories, F.text == "➕ Создать встречу")
async def create_event_start(message: Message, state: FSMContext, session: AsyncSession):
    event_svc = EventService(session)
    user_svc = ProfileService(session)
    user = await user_svc.get_by_tg_id(message.from_user.id)
    existing = await event_svc.get_user_active_event(user.id)
    if existing:
        await message.answer(f"❌ У вас уже есть активная встреча на {existing.event_date.strftime('%d.%m.%Y')}.\nОтмените её в «Мои встречи».")
        return
    categories = await event_svc.get_categories()
    await state.set_state(FindCompany.choosing_category)
    await message.answer("Выберите категорию:", reply_markup=company_categories_kb(categories))

@router.callback_query(FindCompany.choosing_category, F.data.startswith("company_cat:"))
async def category_chosen(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=cat_id)
    await state.set_state(FindCompany.input_date)
    await callback.message.edit_text("📅 Введите дату встречи в формате ДД.ММ.ГГГГ (например, 25.12.2025)")
    await callback.answer()

@router.message(FindCompany.input_date)
async def date_received(message: Message, state: FSMContext):
    try:
        event_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        if event_date < date.today():
            await message.answer("❌ Дата не может быть в прошлом.")
            return
        await state.update_data(event_date=event_date)
        await state.set_state(FindCompany.input_description)
        await message.answer("📝 Напишите краткое описание (до 100 символов):")
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ДД.ММ.ГГГГ")

@router.message(FindCompany.input_description)
async def description_received(message: Message, state: FSMContext):
    desc = message.text.strip()[:100]
    if not desc:
        await message.answer("❌ Описание не может быть пустым.")
        return
    await state.update_data(description=desc)
    data = await state.get_data()
    # достаём категорию (для красоты)
    from bot.database import AsyncSessionFactory
    async with AsyncSessionFactory() as session:
        event_svc = EventService(session)
        cat = await event_svc.get_category_by_id(data['category_id'])
        cat_name = cat.name if cat else "?"
    await state.set_state(FindCompany.confirm)
    await message.answer(
        f"📋 <b>Подтвердите создание:</b>\n\n"
        f"Категория: {cat_name}\n"
        f"Дата: {data['event_date'].strftime('%d.%m.%Y')}\n"
        f"Описание: {desc}\n\n"
        f"Создать?",
        parse_mode="HTML",
        reply_markup=company_confirm_kb()
    )

@router.callback_query(FindCompany.confirm, F.data == "company_confirm:yes")
async def confirm_yes(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    user_svc = ProfileService(session)
    event_svc = EventService(session)
    user = await user_svc.get_by_tg_id(callback.from_user.id)
    cat = await event_svc.get_category_by_id(data['category_id'])
    cat_name = cat.name if cat else "Встреча"
    event = await event_svc.create_event(
        creator_id=user.id,
        category_id=data['category_id'],
        city=user.city,
        event_date=data['event_date'],
        description=data['description']
    )
    await state.set_state(FindCompany.browsing_categories)
    await callback.message.edit_text(
        f"✅ <b>Встреча создана!</b>\n\n"
        f"📌 {cat_name}\n"
        f"📅 {data['event_date'].strftime('%d.%m.%Y')}\n"
        f"📝 {data['description']}\n\n"
        f"📌 <b>Инструкция для организатора:</b>\n"
        f"• Создайте чат (обычную группу) и приглашайте туда всех, кто вам напишет.\n"
        f"• Встреча будет видна в поиске до {data['event_date'].strftime('%d.%m.%Y')}.\n"
        f"• После этой даты она автоматически удалится.",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(FindCompany.confirm, F.data == "company_confirm:no")
async def confirm_no(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FindCompany.browsing_categories)
    await callback.message.edit_text("❌ Создание отменено.")
    await callback.answer()

# ---------- Поиск встреч ----------
@router.message(FindCompany.browsing_categories, F.text == "🔍 Найти встречу")
async def find_event_start(message: Message, state: FSMContext, session: AsyncSession):
    event_svc = EventService(session)
    categories = await event_svc.get_categories()
    await state.set_state(FindCompany.browsing_categories)
    await message.answer(
        "Выберите категорию для поиска:",
        reply_markup=company_categories_kb(categories, for_search=True)
    )


@router.callback_query(FindCompany.browsing_categories, F.data.startswith("company_cat:"))
async def show_events(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    cat_value = callback.data.split(":")[1]

    user_svc = ProfileService(session)
    event_svc = EventService(session)
    user = await user_svc.get_by_tg_id(callback.from_user.id)

    # Если выбрано "Все события"
    if cat_value == "all":
        # Получаем все категории и собираем события из каждой
        categories = await event_svc.get_categories()
        events = []
        for cat in categories:
            # Пропускаем саму категорию "Все события" (если есть)
            if cat.name == "Все события":
                continue
            cat_events = await event_svc.get_events_by_category(cat.id, user.city)
            events.extend(cat_events)
        # Сортируем по дате
        events.sort(key=lambda x: x.event_date)
    else:
        cat_id = int(cat_value)
        events = await event_svc.get_events_by_category(cat_id, user.city)

    if not events:
        await callback.message.edit_text("😔 Нет активных встреч.")
        await callback.answer()
        return

    await callback.message.edit_text("🔍 Найденные встречи:")
    for ev in events:
        # Получаем название категории для отображения
        cat = await event_svc.get_category_by_id(ev.category_id)
        cat_name = cat.name if cat else "?"
        text = f"📌 {cat_name}\n📅 {ev.event_date.strftime('%d.%m.%Y')}\n📝 {ev.description}"
        await callback.message.answer(text, reply_markup=company_event_kb(ev.id))
    await callback.answer()


@router.callback_query(F.data.startswith("company_contact:"))
async def contact_organizer(callback: CallbackQuery, session: AsyncSession):
    event_id = int(callback.data.split(":")[1])

    from bot.services.event_service import EventService

    event_svc = EventService(session)
    event = await event_svc.get_event_by_id(event_id)  # ← теперь creator загружен!

    if not event or not event.is_active:
        await callback.answer("❌ Это событие уже неактивно.", show_alert=True)
        return

    # event.creator уже загружен через selectinload
    creator_link = f"tg://user?id={event.creator.tg_id}"

    await callback.message.answer(
        f"👤 <b>Организатор встречи</b>\n\n"
        f"📅 Дата: {event.event_date.strftime('%d.%m.%Y')}\n"
        f"📝 {event.description}\n\n"
        f"🔗 <a href='{creator_link}'>Нажмите сюда</a>, чтобы написать организатору.\n\n"
        f"💬 Представьтесь и напишите, что хотите присоединиться!",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    await callback.answer()

# ---------- Мои встречи ----------
@router.message(FindCompany.browsing_categories, F.text == "📋 Мои встречи")
async def my_events(message: Message, state: FSMContext, session: AsyncSession):
    user_svc = ProfileService(session)
    event_svc = EventService(session)
    user = await user_svc.get_by_tg_id(message.from_user.id)
    event = await event_svc.get_user_active_event(user.id)
    if not event:
        await message.answer("📭 У вас нет активных встреч.")
        return
    await message.answer(
        f"📌 <b>Ваша встреча:</b>\n\n"
        f"📅 {event.event_date.strftime('%d.%m.%Y')}\n"
        f"📝 {event.description}\n\n"
        f"Люди, которые захотят присоединиться, получат ваш контакт.",
        parse_mode="HTML",
        reply_markup=company_my_event_kb(event.id)
    )

@router.callback_query(F.data.startswith("company_cancel:"))
async def cancel_event(callback: CallbackQuery, session: AsyncSession):
    event_id = int(callback.data.split(":")[1])
    event_svc = EventService(session)
    event = await event_svc.get_event_by_id(event_id)
    if not event or event.creator_id != callback.from_user.id:
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    event.is_active = False
    await session.commit()
    await callback.message.edit_text("❌ Встреча отменена.")
    await callback.answer()