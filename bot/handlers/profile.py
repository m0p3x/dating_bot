from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession
from bot.services.referral_service import ReferralService
from bot.states import EditProfile, Browse, SearchSetup
from bot.keyboards import (
    profile_kb, confirm_delete_kb, skip_kb, remove_kb,
    gender_kb, goal_kb, interests_kb, subscription_kb, main_menu_kb,
    profile_preview_kb, profile_only_kb,
)
from bot.services.profile_service import ProfileService
from bot.services.premium_service import PremiumService
from bot.services.match_service import MatchService
from bot.utils.formatters import format_profile, format_subscription_info, format_premium_upsell, send_media
from bot.config import settings

router = Router()


# ──────────────────────────────────────────────
# Главное меню профиля
# ──────────────────────────────────────────────

@router.message(F.text == "👤 Мой профиль")
async def my_profile(message: Message, session: AsyncSession, state: FSMContext):
    svc = ProfileService(session)
    user = await svc.get_by_tg_id(message.from_user.id)
    if user is None:
        await message.answer("Анкета не найдена. Используй /start.")
        return

    premium_svc = PremiumService(session)
    await premium_svc.check_and_expire(user)

    await state.set_state(None)
    await message.answer("💎", reply_markup=profile_only_kb())
    await message.answer(
        f"<b>Профиль:</b>",
        parse_mode="HTML",
        reply_markup=profile_kb(user.has_premium, user.is_active),
    )

@router.callback_query(F.data == "profile:preview")
async def profile_preview(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    svc = ProfileService(session)
    user = await svc.get_by_tg_id(callback.from_user.id)
    if user is None:
        await callback.answer("Анкета не найдена.")
        return

    text = format_profile(user)

    if user.photos:
        if len(user.photos) == 1:
            await send_media(bot, callback.from_user.id, user, text)
        else:
            # Медиагруппа — разделяем фото и видео
            from aiogram.types import InputMediaPhoto, InputMediaVideo
            media = []
            for i, p in enumerate(user.photos):
                caption = text if i == 0 else None
                if getattr(p, "media_type", "photo") == "video":
                    media.append(InputMediaVideo(media=p.file_id, caption=caption, parse_mode="HTML"))
                else:
                    media.append(InputMediaPhoto(media=p.file_id, caption=caption, parse_mode="HTML"))
            await bot.send_media_group(chat_id=callback.from_user.id, media=media)
    else:
        await bot.send_message(
            chat_id=callback.from_user.id,
            text=text,
            parse_mode="HTML",
        )

    await bot.send_message(
        chat_id=callback.from_user.id,
        text="Что хочешь изменить?",
        reply_markup=profile_preview_kb(),
    )

    await callback.answer()


# ──────────────────────────────────────────────
# Кто меня лайкнул (только для премиум)
# ──────────────────────────────────────────────

@router.callback_query(F.data == "profile:liked_me")
async def profile_liked_me(callback: CallbackQuery, session: AsyncSession, bot: Bot, state: FSMContext):
    svc = ProfileService(session)
    user = await svc.get_by_tg_id(callback.from_user.id)

    match_svc = MatchService(session, bot)
    likes = await match_svc.get_incoming_likes(user.id)

    if not likes:
        await callback.answer("Пока никто не лайкнул твою анкету.", show_alert=True)
        return

    # Показываем только первую анкету — как в menu_liked_me
    like = likes[0]
    from_user = like.from_user
    is_super = like.type == "super"
    text = format_profile(from_user, is_super=is_super)

    if like.message:
        text += f"\n\n💬 <i>«{like.message}»</i>"

    remaining = len(likes) - 1
    if remaining > 0:
        text += f"\n\n👥 Ещё {remaining} человек(а) лайкнули тебя."

    from bot.keyboards import like_response_kb
    if from_user.photos:
        await bot.send_photo(
            chat_id=callback.from_user.id,
            photo=from_user.photos[0].file_id,
            caption=text,
            reply_markup=like_response_kb(like.id),
            parse_mode="HTML",
        )
    else:
        await bot.send_message(
            chat_id=callback.from_user.id,
            text=text,
            reply_markup=like_response_kb(like.id),
            parse_mode="HTML",
        )
    await callback.answer()


# ──────────────────────────────────────────────
# Буст анкеты
# ──────────────────────────────────────────────

@router.callback_query(F.data == "profile:boost")
async def profile_boost(callback: CallbackQuery, session: AsyncSession):
    svc = ProfileService(session)
    user = await svc.get_by_tg_id(callback.from_user.id)

    premium_svc = PremiumService(session)
    if user.is_boosted:
        await callback.answer("Буст уже активен!", show_alert=True)
        return

    success = await premium_svc.grant_boost(user.tg_id)
    if success:
        await callback.answer("🚀 Буст активирован на 24 часа!", show_alert=True)
    else:
        await callback.answer("Не удалось активировать буст.", show_alert=True)


# ──────────────────────────────────────────────
# Подписка
# ──────────────────────────────────────────────

# @router.message(F.text == "⭐ Подписка")
# @router.callback_query(F.data == "profile:subscription")
# async def profile_subscription(event, session: AsyncSession):
#     text = format_subscription_info()
#     kb = subscription_kb(settings.SUBSCRIPTION_URL)
#
#     if isinstance(event, Message):
#         await event.answer(text, parse_mode="HTML", reply_markup=kb)
#     else:
#         await event.message.answer(text, parse_mode="HTML", reply_markup=kb)
#         await event.answer()


# ──────────────────────────────────────────────
# Пауза анкеты
# ──────────────────────────────────────────────

@router.callback_query(F.data == "profile:pause")
async def profile_pause(callback: CallbackQuery, session: AsyncSession):
    svc = ProfileService(session)
    user = await svc.get_by_tg_id(callback.from_user.id)

    if user.is_active:
        await svc.deactivate(callback.from_user.id)
        msg = "⏸ Анкета скрыта из поиска."
        is_active = False
    else:
        await svc.activate(callback.from_user.id)
        msg = "▶️ Анкета снова видна в поиске."
        is_active = True

    await callback.answer(msg, show_alert=True)
    await callback.message.edit_reply_markup(
        reply_markup=profile_kb(user.has_premium, is_active)
    )

# ──────────────────────────────────────────────
# Удаление анкеты
# ──────────────────────────────────────────────

@router.callback_query(F.data == "profile:delete")
async def profile_delete_confirm(callback: CallbackQuery):
    await callback.message.answer(
        "⚠️ Ты уверен? Анкета будет удалена безвозвратно.",
        reply_markup=confirm_delete_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "profile:delete_confirm")
async def profile_delete_execute(callback: CallbackQuery, session: AsyncSession):
    svc = ProfileService(session)
    await svc.delete_profile(callback.from_user.id)
    await callback.message.edit_text("🗑 Анкета удалена. Используй /start чтобы создать новую.")
    await callback.answer()


@router.callback_query(F.data == "profile:delete_cancel")
async def profile_delete_cancel(callback: CallbackQuery):
    await callback.message.edit_text("Удаление отменено.")
    await callback.answer()


# ──────────────────────────────────────────────
# Редактирование анкеты
# ──────────────────────────────────────────────

@router.callback_query(F.data == "profile:edit")
async def profile_edit_start(callback: CallbackQuery, state: FSMContext):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    fields = [
        ("Имя", "edit_field:name"),
        ("Возраст", "edit_field:age"),
        ("Рост", "edit_field:height"),
        ("Город", "edit_field:city"),
        ("Цель", "edit_field:goal"),
        ("Увлечения", "edit_field:interests"),
        ("О себе", "edit_field:bio"),
        ("Фото", "edit_field:photo"),
    ]
    for label, data in fields:
        builder.button(text=label, callback_data=data)
    builder.adjust(2)

    await callback.message.answer(
        "Что хочешь изменить?",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(EditProfile.choose_field)
    await callback.answer()


@router.callback_query(EditProfile.choose_field, F.data.startswith("edit_field:"))
async def edit_field_choose(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]
    await state.update_data(editing_field=field)

    prompts = {
        "name": ("Введи новое имя:", EditProfile.name, None),
        "age": ("Введи новый возраст:", EditProfile.age, None),
        "height": ("Введи новый рост (или «Пропустить»):", EditProfile.height, skip_kb()),
        "city": ("Введи новый город:", EditProfile.city, remove_kb()),
        "goal": ("Выбери цель:", EditProfile.goal, goal_kb(skip=True)),
        "interests": ("Выбери увлечения:", EditProfile.interests, interests_kb([], skip=True)),
        "bio": ("Напиши о себе (или «Пропустить»):", EditProfile.bio, skip_kb()),
        "photo": ("Отправь новые фото (до 3) или напиши «Готово»/«Пропустить»:", EditProfile.photo, skip_kb()),
    }

    text, new_state, kb = prompts[field]
    await state.set_state(new_state)
    await callback.message.answer(text, reply_markup=kb or remove_kb())
    await callback.answer()


# Обработчики редактирования — текстовые поля

@router.message(EditProfile.name)
async def edit_name(message: Message, state: FSMContext, session: AsyncSession):
    name = message.text.strip()
    if len(name) < 2 or len(name) > 64:
        await message.answer("Имя должно быть от 2 до 64 символов.")
        return
    svc = ProfileService(session)
    await svc.update_field(message.from_user.id, name=name)
    await state.set_state(None)
    await message.answer("✅ Имя обновлено!", reply_markup=main_menu_kb())


@router.message(EditProfile.age)
async def edit_age(message: Message, state: FSMContext, session: AsyncSession):
    if not message.text.isdigit() or not (14 <= int(message.text) <= 100):
        await message.answer("Введи реальный возраст (14–100).")
        return
    svc = ProfileService(session)
    await svc.update_field(message.from_user.id, age=int(message.text))
    await state.set_state(None)
    await message.answer("✅ Возраст обновлён!", reply_markup=main_menu_kb())


@router.message(EditProfile.height, F.text == "Пропустить")
async def edit_height_skip(message: Message, state: FSMContext, session: AsyncSession):
    svc = ProfileService(session)
    await svc.update_field(message.from_user.id, height=None)
    await state.set_state(None)
    await message.answer("✅ Рост убран.", reply_markup=main_menu_kb())


@router.message(EditProfile.height)
async def edit_height(message: Message, state: FSMContext, session: AsyncSession):
    if not message.text.isdigit() or not (100 <= int(message.text) <= 250):
        await message.answer("Введи рост от 100 до 250 см.")
        return
    svc = ProfileService(session)
    await svc.update_field(message.from_user.id, height=int(message.text))
    await state.set_state(None)
    await message.answer("✅ Рост обновлён!", reply_markup=main_menu_kb())


from bot.utils.cities import normalize_city

@router.message(EditProfile.city)
async def edit_city(message: Message, state: FSMContext, session: AsyncSession):
    city = message.text.strip()
    if len(city) > 128:
        await message.answer("Слишком длинное название. Попробуй ещё раз.")
        return

    normalized = normalize_city(city)
    if normalized is None:
        await message.answer(
            "❌ Город не найден в списке. Проверь написание.\n\n"
            "Пожалуйста, укажи реальный город.",
        )
        return

    svc = ProfileService(session)
    await svc.update_field(message.from_user.id, city=normalized)
    await state.set_state(None)
    await message.answer("✅ Город обновлён!", reply_markup=main_menu_kb())


@router.callback_query(EditProfile.goal, F.data.startswith("goal:"))
async def edit_goal(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    goal = callback.data.split(":")[1]
    svc = ProfileService(session)
    await svc.update_field(callback.from_user.id, goal=goal)
    await state.set_state(None)
    await callback.message.edit_text("✅ Цель обновлена!")
    await callback.answer()


@router.callback_query(EditProfile.goal, F.data == "skip")
async def edit_goal_skip(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    svc = ProfileService(session)
    await svc.update_field(callback.from_user.id, goal=None)
    await state.set_state(None)
    await callback.message.edit_text("✅ Цель убрана.")
    await callback.answer()


@router.callback_query(EditProfile.interests, F.data.startswith("interest:"))
async def edit_interest_toggle(callback: CallbackQuery, state: FSMContext):
    interest = callback.data.split(":")[1]
    data = await state.get_data()
    selected: list = data.get("selected_interests", [])
    if interest in selected:
        selected.remove(interest)
    else:
        selected.append(interest)
    await state.update_data(selected_interests=selected)
    await callback.message.edit_reply_markup(reply_markup=interests_kb(selected, skip=True))
    await callback.answer()


@router.callback_query(EditProfile.interests, F.data == "interests_done")
async def edit_interests_done(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    selected = data.get("selected_interests", [])
    svc = ProfileService(session)
    user = await svc.get_by_tg_id(callback.from_user.id)
    await svc.set_tags(user.id, selected)
    await state.set_state(None)
    await callback.message.edit_text("✅ Увлечения обновлены!")
    await callback.answer()


@router.callback_query(EditProfile.interests, F.data == "skip")
async def edit_interests_skip(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    svc = ProfileService(session)
    user = await svc.get_by_tg_id(callback.from_user.id)
    await svc.set_tags(user.id, [])
    await state.set_state(None)
    await callback.message.edit_text("✅ Увлечения убраны.")
    await callback.answer()


@router.message(EditProfile.bio, F.text == "Пропустить")
async def edit_bio_skip(message: Message, state: FSMContext, session: AsyncSession):
    svc = ProfileService(session)
    await svc.update_field(message.from_user.id, bio=None)
    await state.set_state(None)
    await message.answer("✅ Bio убрано.", reply_markup=main_menu_kb())


@router.message(EditProfile.bio)
async def edit_bio(message: Message, state: FSMContext, session: AsyncSession):
    bio = message.text.strip()
    if len(bio) > 500:
        await message.answer(f"Слишком длинно ({len(bio)} симв.). Максимум — 500.")
        return
    svc = ProfileService(session)
    await svc.update_field(message.from_user.id, bio=bio)
    await state.set_state(None)
    await message.answer("✅ Bio обновлено!", reply_markup=main_menu_kb())


@router.message(EditProfile.photo, F.photo)
async def edit_photo_receive(message: Message, state: FSMContext):
    data = await state.get_data()
    photos: list = data.get("photos", [])
    if len(photos) >= 3:
        await message.answer("Максимум 3 файла. Напиши «Готово».")
        return
    photos.append({"file_id": message.photo[-1].file_id, "type": "photo"})
    await state.update_data(photos=photos)
    await message.answer(f"Фото добавлено ({len(photos)}/3). Ещё или напиши «Готово».")


@router.message(EditProfile.photo, F.video)
async def edit_video_receive(message: Message, state: FSMContext):
    data = await state.get_data()
    photos: list = data.get("photos", [])
    if len(photos) >= 3:
        await message.answer("Максимум 3 файла. Напиши «Готово».")
        return
    if message.video.duration > 15:
        await message.answer("⚠️ Видео слишком длинное. Максимум — 15 секунд.")
        return
    photos.append({"file_id": message.video.file_id, "type": "video"})
    await state.update_data(photos=photos)
    await message.answer(f"Видео добавлено ({len(photos)}/3). Ещё или напиши «Готово».")


@router.message(EditProfile.photo, F.text.in_({"Готово", "готово", "Пропустить"}))
async def edit_photo_done(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    photos = data.get("photos", [])
    svc = ProfileService(session)
    user = await svc.get_by_tg_id(message.from_user.id)
    if photos:
        await svc.delete_photos(user.id)
        for i, item in enumerate(photos):
            if isinstance(item, dict):
                await svc.add_photo(user.id, item["file_id"], order=i, media_type=item["type"])
            else:
                await svc.add_photo(user.id, item, order=i, media_type="photo")
    await state.set_state(None)
    await message.answer("✅ Медиа обновлены!", reply_markup=main_menu_kb())

# ──────────────────────────────────────────────
# Создать анкету заново
# ──────────────────────────────────────────────

@router.callback_query(F.data == "profile:recreate")
async def profile_recreate_confirm(callback: CallbackQuery):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, начать заново", callback_data="profile:recreate_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="profile:recreate_cancel"),
    ]])
    await callback.message.answer(
        "🔄 Текущая анкета будет удалена и ты пройдёшь регистрацию заново.\n\n"
        "Лайки, матчи и подписка <b>не сохранятся</b>.\n\n"
        "Продолжить?",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data == "profile:recreate_confirm")
async def profile_recreate_execute(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    from bot.states import Registration
    svc = ProfileService(session)
    await svc.delete_profile(callback.from_user.id)
    await state.set_state(Registration.name)
    await callback.message.edit_text("🗑 Анкета удалена.")
    await callback.message.answer(
        "Давай создадим новую анкету!\n\nКак тебя зовут?",
        reply_markup=remove_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "profile:recreate_cancel")
async def profile_recreate_cancel(callback: CallbackQuery):
    await callback.message.edit_text("Отменено.")
    await callback.answer()

# ──────────────────────────────────────────────
# Статистика
# ──────────────────────────────────────────────

@router.callback_query(F.data == "profile:stats")
async def profile_stats(callback: CallbackQuery, session: AsyncSession):
    from bot.services.stats_service import StatsService
    svc = ProfileService(session)
    stats_svc = StatsService(session)

    user = await svc.get_by_tg_id(callback.from_user.id)
    if user is None:
        await callback.answer("Анкета не найдена.")
        return

    stats = await stats_svc.get_user_stats(user)
    await callback.message.answer(
        stats_svc.format_stats(stats),
        parse_mode="HTML",
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Топ 5 анкет
# ──────────────────────────────────────────────
@router.callback_query(F.data == "profile:referral")
async def profile_referral(callback: CallbackQuery, session: AsyncSession):
    """Показывает реферальную ссылку и статистику"""
    svc = ProfileService(session)
    user = await svc.get_by_tg_id(callback.from_user.id)
    if user is None:
        await callback.answer("Анкета не найдена.")
        return

    referral_svc = ReferralService(session)
    link = await referral_svc.generate_referral_link(user.id)
    stats = await referral_svc.get_referral_stats(user.id)

    text = (
        "🔗 <b>Реферальная программа</b>\n\n"
        f"Пригласи друга в бот и получи <b>{stats['bonus_hours']} часа</b> подписки бесплатно, если он пройдет регистрацию!\n\n"
        f"📎 <b>Твоя ссылка:</b>\n"
        f"<code>{link}</code>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Приглашено друзей: {stats['total']}\n"
        f"• Активировано: {stats['activated']}\n"
        f"• Получено бонусов: {stats['activated'] * stats['bonus_hours']}ч\n\n"
        "💡 <b>Как это работает:</b>\n"
        "1. Отправь ссылку другу\n"
        "2. Друг проходит регистрацию\n"
        "3. Ты получаешь 24 часа подписки!"
    )

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "profile:top5")
async def profile_top5(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    from bot.services.stats_service import StatsService
    stats_svc = StatsService(session)

    rows = await stats_svc.get_top5()

    if not rows:
        await callback.answer("Пока нет анкет.", show_alert=True)
        return

    await callback.message.answer("🏆 <b>Топ 5 анкет по лайкам:</b>", parse_mode="HTML")

    for i, (user, likes_count) in enumerate(rows, start=1):
        text = f"#{i} — {format_profile(user)}\n\n❤️ Лайков: <b>{likes_count}</b>"

        if user.photos and len(user.photos) > 0:
            first = user.photos[0]
            # Определяем тип медиа
            if getattr(first, "media_type", "photo") == "video":
                await bot.send_video(
                    chat_id=callback.from_user.id,
                    video=first.file_id,
                    caption=text,
                    parse_mode="HTML",
                )
            else:
                await bot.send_photo(
                    chat_id=callback.from_user.id,
                    photo=first.file_id,
                    caption=text,
                    parse_mode="HTML",
                )
        else:
            await bot.send_message(
                chat_id=callback.from_user.id,
                text=text,
                parse_mode="HTML",
            )

    await callback.answer()