from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.utils.cities import normalize_city, city_from_coords
from bot.states import Registration
from bot.keyboards import (
    skip_kb, remove_kb, gender_kb, goal_kb, interests_kb, main_menu_kb, INTERESTS_LIST, photo_kb, city_kb
)
from bot.services.profile_service import ProfileService
from bot.services.referral_service import ReferralService

router = Router()


# ──────────────────────────────────────────────
# /start
# ──────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
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
        from bot.utils.formatters import format_profile
        user = await svc.get_by_tg_id(message.from_user.id)
        await message.answer(
            f"С возвращением, <b>{user.name}</b>! 👋",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
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
        "📸 Отправь своё фото/видео (до 15с), до 3 штук.\n"
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
    if len(media) >= 3:
        await message.answer("Максимум 3 файла. Напиши «Готово».")
        return
    media.append({"file_id": message.photo[-1].file_id, "type": "photo"})
    await state.update_data(photos=media)
    await message.answer(f"Фото добавлено ({len(media)}/3). Ещё или напиши «Готово».")


@router.message(Registration.photo, F.video)
async def reg_video_receive(message: Message, state: FSMContext):
    data = await state.get_data()
    media: list = data.get("photos", [])
    if len(media) >= 3:
        await message.answer("Максимум 3 файла. Напиши «Готово».")
        return
    if message.video.duration > 15:
        await message.answer("⚠️ Видео слишком длинное. Максимум — 15 секунд.")
        return
    media.append({"file_id": message.video.file_id, "type": "video"})
    await state.update_data(photos=media)
    await message.answer(f"Видео добавлено ({len(media)}/3). Ещё или напиши «Готово».")

@router.message(Registration.photo, F.text.in_({"Готово", "готово", "Пропустить"}))
async def reg_photo_done(message: Message, state: FSMContext, session: AsyncSession):
    await _finish_registration(message, state, session)


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

    from bot.services.premium_service import PremiumService
    premium_svc = PremiumService(session)
    await premium_svc.grant(user.tg_id, days=3650)

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
        "🎉 Анкета создана! Добро пожаловать.\n\n"
        "Нажми «🔍 Смотреть анкеты» чтобы начать знакомства.",
        reply_markup=main_menu_kb(),
    )
