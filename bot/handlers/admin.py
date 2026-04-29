from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.admin_filter import IsAdmin
from bot.states import AdminStates
from bot.keyboards import admin_menu_kb, admin_report_kb, admin_user_kb
from bot.services.report_service import ReportService
from bot.services.admin_service import AdminService
from bot.utils.formatters import format_profile

router = Router()
router.message.filter(IsAdmin())


# ──────────────────────────────────────────────
# Вход в админку
# ──────────────────────────────────────────────

@router.message(Command("admin"))
async def admin_start(message: Message, state: FSMContext, session: AsyncSession):
    report_svc = ReportService(session)
    pending = await report_svc.pending_count()

    await state.set_state(AdminStates.main)
    await message.answer(
        f"🛠 <b>Админ-панель</b>\n\n"
        f"📋 Жалоб в очереди: <b>{pending}</b>",
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )


# ──────────────────────────────────────────────
# Статистика
# ──────────────────────────────────────────────

@router.callback_query(IsAdmin(), F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, session: AsyncSession):
    svc = AdminService(session)
    stats = await svc.get_stats()
    await callback.message.answer(svc.format_stats(stats), parse_mode="HTML")
    await callback.answer()


# ──────────────────────────────────────────────
# Жалобы
# ──────────────────────────────────────────────

@router.callback_query(IsAdmin(), F.data == "admin:reports")
async def admin_reports(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    report_svc = ReportService(session)
    reports = await report_svc.get_pending()

    if not reports:
        await callback.answer("Жалоб нет.", show_alert=True)
        return

    await callback.message.answer(f"📋 Жалоб в очереди: {len(reports)}")

    # Показываем первые 5
    for report in reports[:5]:
        reported = report.reported_user
        text = (
            f"🚩 <b>Жалоба #{report.id}</b>\n"
            f"На пользователя: <b>{reported.name}</b> (id: {reported.id})\n"
            f"Причина: <b>{report.reason}</b>\n"
        )
        if report.comment:
            text += f"Комментарий: <i>{report.comment}</i>\n"
        text += f"Дата: {report.created_at.strftime('%d.%m.%Y %H:%M')}"

        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=admin_report_kb(report.id, reported.id),
        )

    await callback.answer()


@router.callback_query(IsAdmin(), F.data.startswith("admin_report:"))
async def admin_report_action(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    parts = callback.data.split(":")
    action = parts[1]
    report_id = int(parts[2])
    user_db_id = int(parts[3])

    report_svc = ReportService(session)
    admin_svc = AdminService(session)

    if action == "warn":
        # Находим tg_id пользователя чтобы отправить предупреждение
        from sqlalchemy import select
        from bot.models import User
        result = await session.execute(select(User.tg_id).where(User.id == user_db_id))
        tg_id = result.scalar_one_or_none()
        if tg_id:
            try:
                await bot.send_message(
                    tg_id,
                    "⚠️ Ваша анкета получила жалобу. "
                    "Пожалуйста, соблюдайте правила сервиса.",
                )
            except Exception:
                pass
        await report_svc.resolve(report_id)
        await callback.answer("Предупреждение отправлено.", show_alert=True)

    elif action == "ban_temp":
        await admin_svc.ban(user_db_id)
        await report_svc.resolve(report_id)
        await callback.answer("Пользователь забанен.", show_alert=True)

    elif action == "ban_perm":
        await admin_svc.ban(user_db_id)
        await report_svc.resolve(report_id)
        await callback.answer("Пользователь забанен навсегда.", show_alert=True)

    elif action == "delete_profile":
        await admin_svc.delete_profile(user_db_id)
        await report_svc.resolve(report_id)
        await callback.answer("Анкета удалена.", show_alert=True)

    elif action == "dismiss":
        await report_svc.dismiss(report_id)
        await callback.answer("Жалоба отклонена.", show_alert=True)

    await callback.message.edit_reply_markup()


# ──────────────────────────────────────────────
# Поиск пользователя
# ──────────────────────────────────────────────

@router.callback_query(IsAdmin(), F.data == "admin:users")
async def admin_users(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.searching_user)
    await callback.message.answer(
        "Введи @username или tg_id пользователя:"
    )
    await callback.answer()


@router.message(AdminStates.searching_user)
async def admin_user_search(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    admin_svc = AdminService(session)
    user = await admin_svc.find_user(message.text)

    if user is None:
        await message.answer("Пользователь не найден.")
        await state.set_state(AdminStates.main)
        return

    text = (
        f"👤 <b>{user.name}</b>\n"
        f"tg_id: <code>{user.tg_id}</code>\n"
        f"@{user.username or '—'}\n"
        f"Возраст: {user.age}, Пол: {user.gender}\n"
        f"Город: {user.city or '—'}\n"
        f"Активна: {'да' if user.is_active else 'нет'}\n"
        f"Бан: {'да' if user.is_banned else 'нет'}\n"
        f"Премиум: {'да' if user.has_premium else 'нет'}\n"
        f"Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}"
    )

    if user.photos:
        await bot.send_photo(
            chat_id=message.from_user.id,
            photo=user.photos[0].file_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=admin_user_kb(user.id, user.is_banned, user.has_premium),
        )
    else:
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=admin_user_kb(user.id, user.is_banned, user.has_premium),
        )

    await state.set_state(AdminStates.main)


@router.callback_query(IsAdmin(), F.data.startswith("admin_user:"))
async def admin_user_action(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    action = parts[1]
    user_db_id = int(parts[2])

    admin_svc = AdminService(session)
    from sqlalchemy import select
    from bot.models import User
    result = await session.execute(select(User.tg_id).where(User.id == user_db_id))
    tg_id = result.scalar_one_or_none()

    if action == "ban":
        await admin_svc.ban(user_db_id)
        await callback.answer("Пользователь забанен.", show_alert=True)
    elif action == "unban":
        await admin_svc.unban(user_db_id)
        await callback.answer("Пользователь разбанен.", show_alert=True)
    elif action == "give_premium":
        if tg_id:
            await admin_svc.give_premium(tg_id)
        await callback.answer("Подписка выдана на 30 дней.", show_alert=True)
    elif action == "remove_premium":
        if tg_id:
            await admin_svc.remove_premium(tg_id)
        await callback.answer("Подписка снята.", show_alert=True)
    elif action == "delete":
        await admin_svc.delete_profile(user_db_id)
        await callback.answer("Анкета удалена.", show_alert=True)

    await callback.message.edit_reply_markup()


# ──────────────────────────────────────────────
# Рассылка
# ──────────────────────────────────────────────

@router.callback_query(IsAdmin(), F.data == "admin:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.broadcast_text)
    await callback.message.answer(
        "📢 Введи текст рассылки (поддерживается HTML).\n"
        "Для отмены напиши /cancel."
    )
    await callback.answer()


@router.message(AdminStates.broadcast_text, F.text)
async def admin_broadcast_text(message: Message, state: FSMContext):
    await state.update_data(broadcast_text=message.text)
    await state.set_state(AdminStates.broadcast_confirm)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast:confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast:cancel"),
    ]])
    await message.answer(
        f"Предпросмотр:\n\n{message.text}\n\nОтправить всем активным пользователям?",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(IsAdmin(), F.data == "broadcast:confirm")
async def admin_broadcast_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    data = await state.get_data()
    text = data.get("broadcast_text", "")

    from sqlalchemy import select
    from bot.models import User
    result = await session.execute(
        select(User.tg_id).where(User.is_active.is_(True), User.is_banned.is_(False))
    )
    tg_ids = result.scalars().all()

    await callback.message.edit_text(f"📢 Начинаю рассылку... ({len(tg_ids)} пользователей)")

    sent, failed = 0, 0
    for tg_id in tg_ids:
        try:
            await bot.send_message(tg_id, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await state.set_state(AdminStates.main)
    await callback.message.answer(
        f"✅ Рассылка завершена.\nОтправлено: {sent}\nОшибок: {failed}"
    )
    await callback.answer()


@router.callback_query(IsAdmin(), F.data == "broadcast:cancel")
async def admin_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.main)
    await callback.message.edit_text("Рассылка отменена.")
    await callback.answer()


@router.message(Command("cancel"))
async def admin_cancel(message: Message, state: FSMContext):
    await state.set_state(AdminStates.main)
    await message.answer("Действие отменено.", reply_markup=admin_menu_kb())
