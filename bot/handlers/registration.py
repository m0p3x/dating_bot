from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from bot.keyboards import main_menu_kb_with_webapp
from bot.utils.cities import normalize_city, city_from_coords
from bot.states import Registration
from bot.keyboards import (
    skip_kb, remove_kb, gender_kb, goal_kb, interests_kb,
    INTERESTS_LIST, photo_kb, city_kb, terms_kb
)
from bot.services.profile_service import ProfileService
from bot.services.referral_service import ReferralService

router = Router()


# ──────────────────────────────────────────────
# /start
# ──────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("user_"):
        user_id = args[1].replace("user_", "")
        await message.answer(
            f"👤 Профиль пользователя: {user_id}\n\nСвяжитесь с ним в Telegram по этой ссылке: tg://user?id={user_id}")
        return
    # Проверяем реферальный код
    args = message.text.split()
    referrer_code = None
    if len(args) > 1:
        referrer_code = args[1]

    # Сохраняем реферальный код в состояние (если есть)
    if referrer_code and referrer_code.startswith("ref_"):
        await state.update_data(referrer_code=referrer_code)

    svc = ProfileService(session)
    if await svc.exists(message.from_user.id):
        user = await svc.get_by_tg_id(message.from_user.id)
        await message.answer(
            f"С возвращением, {user.name}! 👋",
            reply_markup=main_menu_kb_with_webapp(user.tg_id)
        )
        return

    await state.set_state(Registration.name)
    await message.answer(
        "👋 Привет! Давай создадим твою анкету.\n\n"
        "Как тебя зовут? ",
        reply_markup=remove_kb(),
    )

# ──────────────────────────────────────────────
# Шаг 1: Имя (обязательно)
# ──────────────────────────────────────────────

@router.message(Registration.name)
async def reg_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2 or len(name) > 64:
        await message.answer("Имя должно быть от 2 до 64 символов. Попробуй ещё раз.")
        return

    await state.update_data(name=name)
    await state.set_state(Registration.age)
    await message.answer("Сколько тебе лет?", reply_markup=remove_kb())


# ──────────────────────────────────────────────
# Шаг 2: Возраст (обязательно)
# ──────────────────────────────────────────────

@router.message(Registration.age)
async def reg_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи возраст цифрами, например: 22")
        return

    age = int(message.text)
    if age < 14 or age > 100:
        await message.answer("Укажи реальный возраст (от 14 до 100).")
        return

    await state.update_data(age=age)
    await state.set_state(Registration.gender)
    await message.answer("Укажи свой пол:", reply_markup=gender_kb(skip=False))


# ──────────────────────────────────────────────
# Шаг 3: Пол (обязательно, inline)
# ──────────────────────────────────────────────

@router.callback_query(Registration.gender, F.data.startswith("gender:"))
async def reg_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split(":")[1]  # 'M' или 'F'
    await state.update_data(gender=gender)
    await state.set_state(Registration.height)
    await callback.message.edit_text(
        "📏 Укажи свой рост в сантиметрах (например: 175)\n\n"
        "Или нажми «Пропустить».",
    )
    await callback.message.answer("↓", reply_markup=skip_kb())
    await callback.answer()


# ──────────────────────────────────────────────
# Шаг 4: Рост (пропускаемый)
# ──────────────────────────────────────────────

@router.message(Registration.height, F.text == "Пропустить")
async def reg_height_skip(message: Message, state: FSMContext):
    await state.update_data(height=None)
    await _ask_city(message, state)


@router.message(Registration.height)
async def reg_height(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи рост цифрами, например: 175\nИли нажми «Пропустить».")
        return

    height = int(message.text)
    if height < 100 or height > 250:
        await message.answer("Укажи реальный рост (от 100 до 250 см).")
        return

    await state.update_data(height=height)
    await _ask_city(message, state)


async def _ask_city(message: Message, state: FSMContext):
    await state.set_state(Registration.city)
    await message.answer(
        "📍 В каком городе ты живёшь?\n\n"
        "Напиши название или отправь геолокацию.",
        reply_markup=city_kb(),
    )

@router.message(Registration.city, F.location)
async def reg_city_location(message: Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude

    city = city_from_coords(lat, lon)

    if city:
        await state.update_data(city=city)
        await message.answer(f"📍 Определён город: <b>{city}</b>", parse_mode="HTML")
        await _ask_goal(message, state)
    else:
        await message.answer(
            "❌ Не удалось определить город по геолокации.\n"
            "Пожалуйста, напиши название города вручную (проверь, чтобы не было ошибок!).",
            reply_markup=city_kb(),
        )


@router.message(Registration.city, F.text)
async def reg_city(message: Message, state: FSMContext):
    if not message.text:
        return
    city = message.text.strip()
    if len(city) > 128:
        await message.answer("Название города слишком длинное. Попробуй ещё раз.")
        return

    normalized = normalize_city(city)
    if normalized is None:
        await message.answer(
            "❌ Город не найден. Проверь написание или отправь геолокацию.\n\n"
            "Пожалуйста, укажи реальный город.",
            reply_markup=city_kb(),
        )
        return

    await state.update_data(city=normalized)
    await _ask_goal(message, state)
# ──────────────────────────────────────────────
# Шаг 5: Город (пропускаемый)
# ──────────────────────────────────────────────

async def _ask_goal(message: Message, state: FSMContext):
    await state.set_state(Registration.goal)
    await message.answer(
        "🎯 Что ты ищешь?",
        reply_markup=goal_kb(skip=True),
    )


# ──────────────────────────────────────────────
# Шаг 6: Цель (пропускаемый, inline)
# ──────────────────────────────────────────────

@router.callback_query(Registration.goal, F.data.startswith("goal:"))
async def reg_goal(callback: CallbackQuery, state: FSMContext):
    goal = callback.data.split(":")[1]
    await state.update_data(goal=goal)
    await callback.message.edit_reply_markup()
    await _ask_interests(callback.message, state)
    await callback.answer()


@router.callback_query(Registration.goal, F.data == "skip")
async def reg_goal_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(goal=None)
    await callback.message.edit_reply_markup()
    await _ask_interests(callback.message, state)
    await callback.answer()


async def _ask_interests(message: Message, state: FSMContext):
    await state.set_state(Registration.interests)
    await state.update_data(selected_interests=[])
    await message.answer(
        "🎨 Выбери свои увлечения (можно несколько).\n"
        "Нажми «Готово» когда закончишь.",
        reply_markup=interests_kb(selected=[], skip=True),
    )


# ──────────────────────────────────────────────
# Шаг 7: Увлечения (мульти-выбор, inline)
# ──────────────────────────────────────────────

@router.callback_query(Registration.interests, F.data.startswith("interest:"))
async def reg_interest_toggle(callback: CallbackQuery, state: FSMContext):
    interest = callback.data.split(":")[1]
    data = await state.get_data()
    selected: list = data.get("selected_interests", [])

    if interest in selected:
        selected.remove(interest)
    else:
        selected.append(interest)

    await state.update_data(selected_interests=selected)
    await callback.message.edit_reply_markup(
        reply_markup=interests_kb(selected=selected, skip=True)
    )
    await callback.answer()


@router.callback_query(Registration.interests, F.data == "interests_done")
async def reg_interests_done(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await _ask_bio(callback.message, state)
    await callback.answer()


@router.callback_query(Registration.interests, F.data == "skip")
async def reg_interests_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(selected_interests=[])
    await callback.message.edit_reply_markup()
    await _ask_bio(callback.message, state)
    await callback.answer()


async def _ask_bio(message: Message, state: FSMContext):
    await state.set_state(Registration.bio)
    await message.answer(
        "📝 Расскажи немного о себе (до 500 символов).\n\n"
        "Или нажми «Пропустить».",
        reply_markup=skip_kb(),
    )


# ──────────────────────────────────────────────
# Шаг 8: Bio (пропускаемый)
# ──────────────────────────────────────────────

@router.message(Registration.bio, F.text == "Пропустить")
async def reg_bio_skip(message: Message, state: FSMContext):
    await state.update_data(bio=None)
    await _ask_photo(message, state)


@router.message(Registration.bio)
async def reg_bio(message: Message, state: FSMContext):
    bio = message.text.strip()
    if len(bio) > 500:
        await message.answer(f"Слишком длинно ({len(bio)} символов). Максимум — 500.")
        return
    await state.update_data(bio=bio)
    await _ask_photo(message, state)


async def _ask_photo(message: Message, state: FSMContext):
    await state.set_state(Registration.photo)
    await state.update_data(photos=[])
    await message.answer(
        "📸 Отправь своё фото (1 штуку).\n"
        "Когда закончишь — нажми «Готово».\n\n"
        "Или нажми «Пропустить».",
        reply_markup=photo_kb(),
    )

# ──────────────────────────────────────────────
# Шаг 9: Фото (пропускаемый)
# ──────────────────────────────────────────────

@router.message(Registration.photo, F.photo)
async def reg_photo_receive(message: Message, state: FSMContext):
    data = await state.get_data()
    media: list = data.get("photos", [])
    if len(media) >= 1:
        await message.answer("Максимум 1 фото")
        return
    media.append({"file_id": message.photo[-1].file_id, "type": "photo"})
    await state.update_data(photos=media)
    await message.answer(f"Фото добавлено 1/3). Напиши «Готово».")


# @router.message(Registration.photo, F.video)
# async def reg_video_receive(message: Message, state: FSMContext):
#     data = await state.get_data()
#     media: list = data.get("photos", [])
#     if len(media) >= 3:
#         await message.answer("Максимум 3 файла. Напиши «Готово».")
#         return
#     if message.video.duration > 15:
#         await message.answer("⚠️ Видео слишком длинное. Максимум — 15 секунд.")
#         return
#     media.append({"file_id": message.video.file_id, "type": "video"})
#     await state.update_data(photos=media)
#     await message.answer(f"Видео добавлено ({len(media)}/3). Ещё или напиши «Готово».")

@router.message(Registration.photo, F.text.in_({"Готово", "готово", "Пропустить"}))
async def reg_photo_done(message: Message, state: FSMContext, session: AsyncSession):
    """После фото - показываем соглашение"""
    await _show_terms(message, state)


async def _show_terms(message: Message, state: FSMContext):
    """Показать ссылку на пользовательское соглашение"""
    await state.set_state(Registration.terms)

    from bot.config import settings

    terms_text = (
        "📋 <b>Пользовательское соглашение</b>\n\n"
        f"📄 <a href='{settings.TERMS_URL}'>Нажмите, чтобы прочитать полный текст соглашения</a>\n\n"
        "⚠️ <b>Важно!</b> Если вы не принимаете условия, анкета НЕ будет создана.\n\n"
        "✅ Нажимая «Принимаю условия», вы соглашаетесь с ними."
    )

    await message.answer(
        terms_text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=terms_kb(),
    )


@router.callback_query(Registration.terms, F.data == "terms:accept")
async def terms_accept(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Пользователь принял условия - создаём анкету"""
    await callback.message.edit_reply_markup()  # Убираем кнопки

    # Вызываем finish_registration с правильными параметрами
    await _finish_registration_from_callback(callback, state, session)
    await callback.answer()


@router.callback_query(Registration.terms, F.data == "terms:decline")
async def terms_decline(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Пользователь отказался - возвращаем в начало"""
    await callback.message.edit_reply_markup()
    await state.set_state(None)
    await state.clear()

    await callback.message.answer(
        "❌ Вы не приняли условия пользовательского соглашения.\n\n"
        "Анкета не создана.\n\n"
        "Если передумаете - нажмите /start.",
        reply_markup=remove_kb(),
    )
    await callback.answer()

async def _finish_registration(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    svc = ProfileService(session)

    user = await svc.create(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        name=data["name"],
        age=data["age"],
        gender=data["gender"],
        height=data.get("height"),
        city=data.get("city"),
        goal=data.get("goal"),
        bio=data.get("bio"),
    )


    # Сохраняем фото
    for i, item in enumerate(data.get("photos", [])):
        if isinstance(item, dict):
            await svc.add_photo(user.id, item["file_id"], order=i, media_type=item["type"])
        else:
            await svc.add_photo(user.id, item, order=i, media_type="photo")

    # Сохраняем теги
    interests = data.get("selected_interests", [])
    if interests:
        await svc.set_tags(user.id, interests)

    # Обрабатываем рефералку
    referrer_code = data.get("referrer_code")
    if referrer_code:
        referral_svc = ReferralService(session)
        success = await referral_svc.process_referral(user.id, referrer_code)
        if success:
            await message.answer(
                "🎉 Вы перешли по реферальной ссылке!\n"
                "После завершения регистрации ваш друг получит бонус!"
            )

    # Начисляем бонус пригласившему (после полной регистрации)
    if referrer_code:
        referral_svc = ReferralService(session)
        await referral_svc.grant_referral_bonus(user.id, message.bot)

    await state.set_state(None)
    await message.answer(
        "🎉 Анкета создана! Добро пожаловать...",
        parse_mode="HTML",
        reply_markup=main_menu_kb_with_webapp(user.tg_id),
    )

async def _finish_registration_from_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Завершает регистрацию после принятия оферты (вызывается из callback)"""
    data = await state.get_data()
    svc = ProfileService(session)

    # ИСПРАВЛЕНО: используем callback.from_user.id (тот, кто нажал кнопку)
    user = await svc.create(
        tg_id=callback.from_user.id,
        username=callback.from_user.username,
        name=data["name"],
        age=data["age"],
        gender=data["gender"],
        height=data.get("height"),
        city=data.get("city"),
        goal=data.get("goal"),
        bio=data.get("bio"),
    )

    # Сохраняем фото
    for i, item in enumerate(data.get("photos", [])):
        if isinstance(item, dict):
            await svc.add_photo(user.id, item["file_id"], order=i, media_type=item["type"])
        else:
            await svc.add_photo(user.id, item, order=i, media_type="photo")

    # Сохраняем теги
    interests = data.get("selected_interests", [])
    if interests:
        await svc.set_tags(user.id, interests)

    # Обрабатываем рефералку
    referrer_code = data.get("referrer_code")
    if referrer_code:
        referral_svc = ReferralService(session)
        success = await referral_svc.process_referral(user.id, referrer_code)
        if success:
            await callback.message.answer(
                "🎉 Вы перешли по реферальной ссылке!\n"
                "После завершения регистрации ваш друг получит бонус!"
            )

    # Начисляем бонус пригласившему (после полной регистрации)
    if referrer_code:
        referral_svc = ReferralService(session)
        await referral_svc.grant_referral_bonus(user.id, callback.bot)

    await state.set_state(None)
    await callback.message.answer(
        "🎉 Анкета создана! Добро пожаловать.\n\n"
        "Нажми «Открыть Mini app» внизу, чтобы начать знакомства.\n\n"
        "❗️ <b>ПОМНИ!</b> что анкеты будут показываться по твоим фильтрам, но если анкеты закончатся, "
        "то фильтры будут убираться по порядку: рост, интересы, цель, возраст",
        parse_mode="HTML",
        reply_markup=main_menu_kb_with_webapp(user.tg_id),
    )

@router.message(CommandStart(deep_link=True))
async def start_with_deeplink(message: Message, state: FSMContext, session: AsyncSession):
    args = message.text.split()
    if len(args) > 1 and args[1] == "company":
        # Переключить пользователя в режим «Найти компанию» (как если бы нажал кнопку в боте)
        await message.answer("👥 Режим «Найти компанию»...")
        # Здесь запускайте существующую логику из company.py
        return
    # обычная регистрация
