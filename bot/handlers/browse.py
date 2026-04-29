from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, InputMediaVideo
from sqlalchemy.ext.asyncio import AsyncSession
from bot.utils.formatters import format_profile, send_media
from bot.states import Browse, SearchSetup
from bot.keyboards import (
    browse_kb, like_received_kb, like_response_kb,
    report_reason_kb, search_gender_kb, subscription_kb, main_menu_kb,
    back_only_kb,
)
from bot.keyboards import change_filters_kb
from bot.services.profile_service import ProfileService
from bot.services.search_service import SearchService
from bot.services.match_service import MatchService
from bot.services.premium_service import PremiumService
from bot.config import settings

router = Router()


# ──────────────────────────────────────────────
# Запуск поиска — настройка фильтров
# ──────────────────────────────────────────────

@router.message(F.text == "🔍 Смотреть анкеты")
async def start_search(message: Message, state: FSMContext, session: AsyncSession):
    svc = ProfileService(session)
    user = await svc.get_by_tg_id(message.from_user.id)
    if user is None:
        await message.answer("Сначала создай анкету командой /start.")
        return

    data = await state.get_data()
    if data.get("filters_set"):
        await state.set_state(Browse.viewing)
        await message.answer("🔍 Ищу анкеты...", reply_markup=main_menu_kb())  # ← добавить
        await _show_next_profile(message, state, session, message.bot, message.from_user.id)
        return

    await _ask_search_gender(message, state)

async def _ask_search_gender(message: Message, state: FSMContext):
    await state.set_state(SearchSetup.gender)
    await state.update_data(
        search_gender=None, search_goal=None,
        search_interests=[], prev_profile_id=None,
    )
    await message.answer("Кого ты хочешь найти?", reply_markup=search_gender_kb())


@router.callback_query(SearchSetup.gender, F.data.startswith("search_gender:"))
async def setup_gender(callback: CallbackQuery, state: FSMContext):
    from bot.keyboards import search_height_skip_kb
    gender = callback.data.split(":")[1]
    await state.update_data(search_gender=None if gender == "any" else gender)
    await state.set_state(SearchSetup.height)
    await callback.message.edit_text(
        "Введи искомый рост в см для фильтрации (будут показываться ±5 см).\n\nИли нажми «Пропустить».",
        reply_markup=search_height_skip_kb(),
    )
    await callback.answer()


@router.message(SearchSetup.height)
async def setup_height_input(message: Message, state: FSMContext):
    from bot.keyboards import search_height_skip_kb
    if not message.text.isdigit() or not (100 <= int(message.text) <= 250):
        await message.answer(
            "Введи рост от 100 до 250 см.\nИли нажми «Пропустить».",
            reply_markup=search_height_skip_kb(),
        )
        return
    await state.update_data(apply_height=True, search_height=int(message.text))
    await message.answer("Что ищешь?", reply_markup=_search_goal_kb())
    await state.set_state(SearchSetup.goal)


@router.callback_query(SearchSetup.height, F.data == "search_skip:height")
async def setup_height_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(apply_height=False, search_height=None)
    await callback.message.edit_text("Что ищешь?", reply_markup=_search_goal_kb())
    await state.set_state(SearchSetup.goal)
    await callback.answer()


def _search_goal_kb():
    from bot.keyboards import search_goal_kb
    return search_goal_kb()


@router.callback_query(SearchSetup.goal, F.data.startswith("search_goal:"))
async def setup_goal(callback: CallbackQuery, state: FSMContext):
    goal = callback.data.split(":")[1]
    await state.update_data(search_goal=goal)
    await _ask_search_interests(callback, state)


@router.callback_query(SearchSetup.goal, F.data == "search_skip:goal")
async def setup_goal_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(search_goal=None)
    await _ask_search_interests(callback, state)


async def _ask_search_interests(callback: CallbackQuery, state: FSMContext):
    from bot.keyboards import search_interests_kb
    await callback.message.edit_text(
        "Выбери увлечения для поиска (или пропусти):",
        reply_markup=search_interests_kb([]),
    )
    await state.set_state(SearchSetup.interests)
    await callback.answer()


@router.callback_query(SearchSetup.interests, F.data.startswith("search_interest:"))
async def setup_interest_toggle(callback: CallbackQuery, state: FSMContext):
    from bot.keyboards import search_interests_kb
    interest = callback.data.split(":")[1]
    data = await state.get_data()
    selected: list = data.get("search_interests", [])
    if interest in selected:
        selected.remove(interest)
    else:
        selected.append(interest)
    await state.update_data(search_interests=selected)
    await callback.message.edit_reply_markup(reply_markup=search_interests_kb(selected))
    await callback.answer()


@router.callback_query(SearchSetup.interests, F.data.in_({"search_interests_done", "search_skip:interests"}))
async def setup_interests_done(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    await callback.message.edit_reply_markup()
    await state.update_data(filters_set=True)
    await state.set_state(Browse.viewing)
    await callback.answer()
    await callback.message.answer("🔍 Начинаю поиск...", reply_markup=main_menu_kb())  # ← добавить
    await _show_next_profile(callback.message, state, session, bot, callback.from_user.id)

@router.callback_query(Browse.viewing, F.data == "browse:change_filters")
async def browse_change_filters(callback: CallbackQuery, state: FSMContext):
    await state.update_data(filters_set=False)
    await callback.message.edit_reply_markup()
    await callback.answer()
    await _ask_search_gender(callback.message, state)


# ──────────────────────────────────────────────
# Кнопки нижнего меню
# ──────────────────────────────────────────────

@router.message(Browse.viewing, F.text == "👍 Лайк")
async def menu_like(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    data = await state.get_data()
    profile_svc = ProfileService(session)
    viewer = await profile_svc.get_by_tg_id(message.from_user.id)
    candidate = await profile_svc.get_by_id(data.get("current_profile_id"))
    if candidate is None:
        await message.answer("Нет активной анкеты.")
        return
    match_svc = MatchService(session, bot)
    await match_svc.send_like(viewer, candidate, like_type="like")
    await message.answer("❤️ Лайк отправлен!")
    await _show_next_profile(message, state, session, bot, message.from_user.id)


@router.message(Browse.viewing, F.text == "⏭ Пропуск")
async def menu_skip(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    from bot.keyboards import skipped_kb
    data = await state.get_data()
    current_id = data.get("current_profile_id")
    prev_msg_id = data.get("prev_msg_id")

    profile_svc = ProfileService(session)
    viewer = await profile_svc.get_by_tg_id(message.from_user.id)

    # Добавляем кнопку "Вернуться" к предыдущей анкете
    if current_id and prev_msg_id:
        try:
            await bot.edit_message_reply_markup(
                chat_id=message.from_user.id,
                message_id=prev_msg_id,
                reply_markup=skipped_kb(current_id, viewer.has_premium),
            )
        except Exception:
            pass

    await _show_next_profile(message, state, session, bot, message.from_user.id)

@router.message(Browse.viewing_likes, F.text == "👍 Лайк")
async def likes_like_btn(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    data = await state.get_data()
    like_id = data.get("current_like_id")
    if not like_id:
        await message.answer("Что-то пошло не так.", reply_markup=main_menu_kb())
        await state.set_state(Browse.viewing)
        return
    profile_svc = ProfileService(session)
    viewer = await profile_svc.get_by_tg_id(message.from_user.id)
    match_svc = MatchService(session, bot)
    await match_svc.mark_like_viewed(like_id)
    matched = await match_svc.reply_like(like_id, viewer)
    if matched:
        await message.answer("🎉 Матч!", reply_markup=main_menu_kb())
    else:
        await message.answer("❤️ Лайк отправлен!", reply_markup=main_menu_kb())
    await state.set_state(None)

@router.message(Browse.viewing_likes, F.text == "⏭ Пропуск")
async def likes_skip_btn(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    data = await state.get_data()
    like_id = data.get("current_like_id")

    profile_svc = ProfileService(session)
    user = await profile_svc.get_by_tg_id(message.from_user.id)
    match_svc = MatchService(session, bot)
    await match_svc.mark_like_viewed(like_id)  # ← добавить
    likes = await match_svc.get_incoming_likes(user.id)
    likes = [l for l in likes if l.id != like_id]

    if not likes:
        await message.answer("Все лайки просмотрены.", reply_markup=main_menu_kb())
        await state.set_state(None)
        return

    like = likes[0]
    from_user = like.from_user
    is_super = like.type == "super"
    text = format_profile(from_user, is_super=is_super)
    if like.message:
        text += f"\n\n💬 <i>«{like.message}»</i>"
    remaining = len(likes) - 1
    if remaining > 0:
        text += f"\n\n👥 Ещё {remaining} человек(а) лайкнули тебя."

    if from_user.photos:
        await bot.send_photo(
            chat_id=message.from_user.id,
            photo=from_user.photos[0].file_id,
            caption=text,
            reply_markup=like_response_kb(like.id),
            parse_mode="HTML",
        )
    else:
        await bot.send_message(
            chat_id=message.from_user.id,
            text=text,
            reply_markup=like_response_kb(like.id),
            parse_mode="HTML",
        )

    await state.update_data(current_like_id=like.id)

@router.message(F.text == "❤️ Кто меня лайкнул")
async def menu_liked_me(message: Message, session: AsyncSession, bot: Bot, state: FSMContext):
    await state.set_state(Browse.viewing_likes)
    await message.answer("⬇️", reply_markup=main_menu_kb())
    profile_svc = ProfileService(session)
    user = await profile_svc.get_by_tg_id(message.from_user.id)
    if user is None:
        return

    match_svc = MatchService(session, bot)
    likes = await match_svc.get_incoming_likes(user.id)

    if not likes:
        await message.answer("😔 Пока никто не лайкнул твою анкету.")
        return

    like = likes[0]
    from_user = like.from_user
    is_super = like.type == "super"
    text = format_profile(from_user, is_super=is_super)

    if like.message:
        text += f"\n\n💬 <i>«{like.message}»</i>"

    remaining = len(likes) - 1
    if remaining > 0:
        text += f"\n\n👥 Ещё {remaining} человек(а) лайкнули тебя."

    if from_user.photos:
        first = from_user.photos[0]
        if getattr(first, "media_type", "photo") == "video":
            await bot.send_video(
                chat_id=message.from_user.id,  # ✅ ИСПРАВЛЕНО
                video=first.file_id,
                caption=text,
                parse_mode="HTML",
            )
        else:
            await bot.send_photo(
                chat_id=message.from_user.id,  # ✅ ИСПРАВЛЕНО
                photo=first.file_id,
                caption=text,
                parse_mode="HTML",
            )
    else:
        await bot.send_message(
            chat_id=message.from_user.id,  # ✅ ИСПРАВЛЕНО
            text=text,
            parse_mode="HTML",
        )
    await state.update_data(current_like_id=like.id)
    await state.set_state(Browse.viewing_likes)
# ──────────────────────────────────────────────
# Показ анкеты
# ──────────────────────────────────────────────

async def _show_next_profile(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    tg_id: int,
):
    profile_svc = ProfileService(session)
    search_svc = SearchService(session)
    premium_svc = PremiumService(session)

    viewer = await profile_svc.get_by_tg_id(tg_id)
    if viewer is None:
        return

    await premium_svc.check_and_expire(viewer)
    await premium_svc.check_and_expire_boost(viewer)

    data = await state.get_data()

    candidate = await search_svc.get_next_profile(
        viewer=viewer,
        search_gender=data.get("search_gender"),
        search_goal=data.get("search_goal"),
        search_interests=data.get("search_interests") or [],
        apply_height=data.get("apply_height", False),
        search_height=data.get("search_height"),
    )

    if candidate is None:
        search_gender = data.get("search_gender")

        if search_gender == "F":
            message_text = "😔 Анкеты девушек закончились.\n\nПопробуй изменить фильтры или зайди позже!"
        elif search_gender == "M":
            message_text = "😔 Анкеты парней закончились.\n\nПопробуй изменить фильтры или зайди позже!"
        else:
            message_text = "😔 Анкеты по твоим фильтрам закончились.\n\nПопробуй изменить фильтры или зайди позже!"

        await message.answer(
            message_text,
            reply_markup=change_filters_kb()
        )
        await state.set_state(None)
        return

    prev_id = data.get("current_profile_id")
    await state.update_data(
        current_profile_id=candidate.id,
        prev_profile_id=prev_id,
    )

    await search_svc.mark_viewed(viewer.id, candidate.id)

    text = format_profile(candidate)
    kb = browse_kb(has_premium=viewer.has_premium)
    sent_msg = None

    if candidate.photos:
        if len(candidate.photos) == 1:
            first = candidate.photos[0]
            if getattr(first, "media_type", "photo") == "video":
                sent_msg = await bot.send_video(
                    chat_id=tg_id, video=first.file_id,
                    caption=text, reply_markup=kb, parse_mode="HTML",
                )
            else:
                sent_msg = await bot.send_photo(
                    chat_id=tg_id, photo=first.file_id,
                    caption=text, reply_markup=kb, parse_mode="HTML",
                )
        else:
            media = []
            for i, p in enumerate(candidate.photos):
                caption = text if i == 0 else None
                if getattr(p, "media_type", "photo") == "video":
                    media.append(InputMediaVideo(media=p.file_id, caption=caption, parse_mode="HTML"))
                else:
                    media.append(InputMediaPhoto(media=p.file_id, caption=caption, parse_mode="HTML"))
            await bot.send_media_group(chat_id=tg_id, media=media)
            sent_msg = await bot.send_message(chat_id=tg_id, text="⬆️ Действия:", reply_markup=kb)
    else:
        sent_msg = await bot.send_message(
            chat_id=tg_id, text=text, reply_markup=kb, parse_mode="HTML"
        )

    if sent_msg:
        await state.update_data(prev_msg_id=sent_msg.message_id)

# ──────────────────────────────────────────────
# Действия при просмотре анкеты
# ──────────────────────────────────────────────

@router.callback_query(Browse.viewing, F.data == "browse:skip")
async def browse_skip(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    from bot.keyboards import skipped_kb
    data = await state.get_data()
    current_id = data.get("current_profile_id")
    profile_svc = ProfileService(session)
    viewer = await profile_svc.get_by_tg_id(callback.from_user.id)
    if current_id:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=skipped_kb(current_id, viewer.has_premium)
            )
        except Exception:
            pass
    await callback.answer()
    await _show_next_profile(callback.message, state, session, bot, callback.from_user.id)


@router.callback_query(Browse.viewing, F.data == "browse:like")
async def browse_like(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    await _handle_like(callback, state, session, bot, like_type="like")

@router.callback_query(F.data == "browse:change_filters")
async def browse_change_filters_global(callback: CallbackQuery, state: FSMContext):
    await state.update_data(filters_set=False)
    await callback.message.edit_reply_markup()
    await callback.answer()
    await _ask_search_gender(callback.message, state)

@router.callback_query(Browse.viewing, F.data == "browse:super")
async def browse_super(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    profile_svc = ProfileService(session)
    viewer = await profile_svc.get_by_tg_id(callback.from_user.id)
    match_svc = MatchService(session, bot)
    if not await match_svc.can_send_super_like(viewer):
        await callback.answer(
            "Лимит суперлайков на сегодня исчерпан. Оформи подписку! ⭐",
            show_alert=True,
        )
        return
    await _handle_like(callback, state, session, bot, like_type="super")


@router.callback_query(Browse.viewing, F.data == "browse:message")
async def browse_message_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    profile_svc = ProfileService(session)
    viewer = await profile_svc.get_by_tg_id(callback.from_user.id)
    match_svc = MatchService(session, bot)
    if not await match_svc.can_send_message_like(viewer):
        await callback.answer(
            f"Лимит лайков с сообщением на сегодня исчерпан "
            f"({settings.MSG_LIKE_DAILY_LIMIT}/день). Оформи подписку! ⭐",
            show_alert=True,
        )
        return
    await state.set_state(Browse.writing_message)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data="browse:message_cancel")
    ]])
    await callback.message.answer(
        "✍️ Напиши сообщение для этого человека (до 300 символов):",
        reply_markup=cancel_kb,
    )
    await callback.answer()


@router.callback_query(Browse.writing_message, F.data == "browse:message_cancel")
async def browse_message_cancel(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Browse.viewing)
    await callback.message.edit_text("Отменено.")
    await callback.answer()


@router.message(Browse.writing_message)
async def browse_message_send(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    text = message.text.strip() if message.text else ""
    if len(text) > 300:
        await message.answer(f"Слишком длинно ({len(text)} симв.). Максимум — 300.")
        return
    if not text:
        await message.answer("Сообщение не может быть пустым.")
        return
    data = await state.get_data()
    profile_svc = ProfileService(session)
    viewer = await profile_svc.get_by_tg_id(message.from_user.id)
    candidate = await profile_svc.get_by_id(data["current_profile_id"])
    if candidate is None:
        await state.set_state(Browse.viewing)
        return
    match_svc = MatchService(session, bot)
    await match_svc.send_like(viewer, candidate, like_type="message", message=text)
    await state.set_state(Browse.viewing)
    await message.answer("💬 Сообщение отправлено!")
    await _show_next_profile(message, state, session, bot, message.from_user.id)


async def _handle_like(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    like_type: str,
):
    data = await state.get_data()
    profile_svc = ProfileService(session)
    viewer = await profile_svc.get_by_tg_id(callback.from_user.id)
    candidate = await profile_svc.get_by_id(data["current_profile_id"])
    if candidate is None:
        await callback.answer("Анкета уже недоступна.")
        await _show_next_profile(callback.message, state, session, bot, callback.from_user.id)
        return
    match_svc = MatchService(session, bot)
    await match_svc.send_like(viewer, candidate, like_type=like_type)
    await callback.message.edit_reply_markup()
    await callback.answer("❤️ Лайк отправлен!")
    await _show_next_profile(callback.message, state, session, bot, callback.from_user.id)


# ──────────────────────────────────────────────
# Вернуться к пропущенной анкете
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("browse:return:"))
async def browse_return(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    profile_id = int(callback.data.split(":")[2])
    profile_svc = ProfileService(session)
    viewer = await profile_svc.get_by_tg_id(callback.from_user.id)
    candidate = await profile_svc.get_by_id(profile_id)
    if candidate is None:
        await callback.answer("Анкета уже недоступна.", show_alert=True)
        return

    # Проверяем — не лайкал ли уже эту анкету
    from sqlalchemy import select
    from bot.models import Like
    existing_like = await session.execute(
        select(Like.id).where(
            Like.from_id == viewer.id,
            Like.to_id == candidate.id,
        )
    )
    if existing_like.scalar_one_or_none() is not None:
        await callback.answer("Ты уже оценил эту анкету.", show_alert=True)
        await callback.message.edit_reply_markup()
        return

    # Удаляем текущую анкету из viewed
    data = await state.get_data()
    current_id = data.get("current_profile_id")
    if current_id and current_id != profile_id:
        from sqlalchemy import delete
        from bot.models import Viewed
        await session.execute(
            delete(Viewed).where(
                Viewed.viewer_id == viewer.id,
                Viewed.viewed_id == current_id,
            )
        )
        await session.commit()

    text = format_profile(candidate)
    kb = browse_kb(has_premium=viewer.has_premium)

    await state.update_data(
        current_profile_id=candidate.id,
        prev_profile_id=None,
        prev_msg_id=None,
    )
    await state.set_state(Browse.viewing)

    sent_msg = await send_media(bot, callback.from_user.id, candidate, text, reply_markup=kb)
    if sent_msg:
        await state.update_data(prev_msg_id=sent_msg.message_id)

    await callback.message.edit_reply_markup()
    await callback.answer()

# ──────────────────────────────────────────────
# Премиум-заглушка
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("premium:"))
async def premium_gate(callback: CallbackQuery):
    await callback.answer(
        "🔒 Чтобы пользоваться данной функцией, "
        "приобретите подписку всего за 39 рублей в месяц!",
        show_alert=True,
    )


# ──────────────────────────────────────────────
# Ответ на входящий лайк
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("like_view:"))
async def like_view(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    like_id = int(callback.data.split(":")[1])
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from bot.models import Like, User, UserTag

    result = await session.execute(
        select(Like)
        .where(Like.id == like_id)
        .options(
            selectinload(Like.from_user).selectinload(User.photos),
            selectinload(Like.from_user).selectinload(User.tags).selectinload(UserTag.tag),
        )
    )
    like = result.scalar_one_or_none()
    if like is None or like.is_mutual:
        await callback.answer("Лайк уже не актуален.")
        return

    from_user = like.from_user
    is_super = like.type == "super"
    text = format_profile(from_user, is_super=is_super)
    if like.message:
        text += f"\n\n💬 <i>«{like.message}»</i>"

    if from_user.photos:
        first = from_user.photos[0]
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

    # Переключаем состояние и сохраняем like_id
    await state.update_data(current_like_id=like_id)
    await state.set_state(Browse.viewing_likes)
    await bot.send_message(
        chat_id=callback.from_user.id,
        text="👆 Оцени эту анкету:",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("like_reply:"))
async def like_reply(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    like_id = int(callback.data.split(":")[1])
    profile_svc = ProfileService(session)
    viewer = await profile_svc.get_by_tg_id(callback.from_user.id)
    match_svc = MatchService(session, bot)
    matched = await match_svc.reply_like(like_id, viewer)
    await callback.message.edit_reply_markup()
    if matched:
        await callback.answer("🎉 Матч!", show_alert=True)
    else:
        await callback.answer("Что-то пошло не так.")


@router.callback_query(F.data.startswith("like_skip:"))
async def like_skip(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    like_id = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup()

    profile_svc = ProfileService(session)
    user = await profile_svc.get_by_tg_id(callback.from_user.id)
    match_svc = MatchService(session, bot)
    await match_svc.mark_like_viewed(like_id)  # ← добавить
    likes = await match_svc.get_incoming_likes(user.id)
    likes = [l for l in likes if l.id != like_id]

    if not likes:
        await callback.answer("Больше лайков нет.", show_alert=True)
        await state.set_state(Browse.viewing)
        await bot.send_message(
            chat_id=callback.from_user.id,
            text="Все лайки просмотрены.",
            reply_markup=main_menu_kb(),
        )
        return

    like = likes[0]
    from_user = like.from_user
    is_super = like.type == "super"
    text = format_profile(from_user, is_super=is_super)
    if like.message:
        text += f"\n\n💬 <i>«{like.message}»</i>"
    remaining = len(likes) - 1
    if remaining > 0:
        text += f"\n\n👥 Ещё {remaining} человек(а) лайкнули тебя."

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

    await state.update_data(current_like_id=like.id)
    await callback.answer()

# ──────────────────────────────────────────────
# Жалоба
# ──────────────────────────────────────────────

@router.callback_query(Browse.viewing, F.data == "browse:report")
async def browse_report_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Browse.reporting)
    await callback.message.answer(
        "🚩 Выбери причину жалобы:",
        reply_markup=report_reason_kb(),
    )
    await callback.answer()


@router.callback_query(Browse.reporting, F.data.startswith("report_reason:"))
async def browse_report_reason(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    reason = callback.data.split(":")[1]
    if reason == "other":
        await state.update_data(report_reason="other")
        await state.set_state(Browse.report_comment)
        await callback.message.answer("✍️ Опиши проблему кратко:")
        await callback.answer()
        return
    await _submit_report(callback, state, session, bot, reason=reason, comment=None)


@router.message(Browse.report_comment)
async def browse_report_comment(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    comment = message.text.strip()[:500]
    await _submit_report_from_message(message, state, session, bot, comment=comment)


async def _submit_report(
    callback: CallbackQuery, state: FSMContext,
    session: AsyncSession, bot: Bot,
    reason: str, comment=None,
):
    from bot.services.report_service import ReportService
    data = await state.get_data()
    current_id = data.get("current_profile_id")
    profile_svc = ProfileService(session)
    viewer = await profile_svc.get_by_tg_id(callback.from_user.id)
    candidate = await profile_svc.get_by_id(current_id) if current_id else None
    if viewer and candidate:
        report_svc = ReportService(session)
        await report_svc.create(from_id=viewer.id, to_id=candidate.id, reason=reason, comment=comment)
        for admin_tg_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_tg_id,
                    f"🚩 Новая жалоба на <b>{candidate.name}</b> (id: {candidate.id})\nПричина: {reason}",
                    parse_mode="HTML",
                )
            except Exception:
                pass
    await state.set_state(Browse.viewing)
    await callback.message.edit_reply_markup()
    await callback.message.answer("✅ Жалоба отправлена. Спасибо!")
    await callback.answer()
    await _show_next_profile(callback.message, state, session, bot, callback.from_user.id)


async def _submit_report_from_message(
    message: Message, state: FSMContext,
    session: AsyncSession, bot: Bot, comment: str,
):
    from bot.services.report_service import ReportService
    data = await state.get_data()
    current_id = data.get("current_profile_id")
    profile_svc = ProfileService(session)
    viewer = await profile_svc.get_by_tg_id(message.from_user.id)
    candidate = await profile_svc.get_by_id(current_id) if current_id else None
    if viewer and candidate:
        report_svc = ReportService(session)
        await report_svc.create(from_id=viewer.id, to_id=candidate.id, reason="other", comment=comment)
    await state.set_state(Browse.viewing)
    await message.answer("✅ Жалоба отправлена. Спасибо!")
    await _show_next_profile(message, state, session, bot, message.from_user.id)
