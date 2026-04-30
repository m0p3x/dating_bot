from typing import Optional

from bot.models import User
from bot.keyboards import GOALS


def format_profile(user: User, is_super: bool = False) -> str:
    """
    Возвращает текст анкеты для отображения пользователю.
    is_super=True — добавляет пометку суперлайка (используется при просмотре входящих).
    """
    lines = []

    if is_super:
        lines.append("⭐ <b>Суперлайк!</b>")
        lines.append("")

    # Имя и возраст — всегда есть
    header = f"<b>{user.name}</b>, {user.age} лет"

    # Пол
    gender_str = "👨 Парень" if user.gender == "M" else "👩 Девушка"
    header += f"  •  {gender_str}"
    lines.append(header)

    # Рост — если есть
    if user.height:
        lines.append(f"📏 Рост: {user.height} см")

    # Город — если есть
    if user.city:
        lines.append(f"📍 {user.city}")

    # Цель — если есть
    if user.goal and user.goal in GOALS:
        lines.append(f"Цель: {GOALS[user.goal]}")

    # Увлечения — если есть
    tag_names = [ut.tag.name for ut in user.tags if ut.tag] if user.tags else []
    if tag_names:
        lines.append(f"Увлечения: {', '.join(tag_names)}")

    # Bio — если есть
    if user.bio:
        lines.append("")
        lines.append(user.bio)

    # Значок подписки
    if user.has_premium:
        lines.append("")
        lines.append("⭐")

    return "\n".join(lines)


def format_premium_upsell(feature_name: Optional[str] = None) -> str:
    """Сообщение при попытке использовать платную функцию без подписки."""
    base = "🔒 Чтобы пользоваться данной функцией, приобретите подписку всего за <b>39 рублей в месяц!</b>"
    return base


def format_subscription_info(user: Optional[User] = None) -> str:
    """Экран описания подписки с информацией о текущей подписке"""
    text = (
        "⭐ <b>Премиум подписка</b>\n\n"
        "С подпиской вы получаете:\n\n"
        "💬 <b>Сообщение</b> — без ограничений\n"
        "   (бесплатно: 3 в день)\n\n"
        "⭐ <b>Суперлайк(тот же лайк, но для особенных)</b> — без ограничений\n"
        "   (бесплатно: 1 в день)\n\n"
        "↩ <b>Возврат к анкете</b> — вернитесь к случайно\n"
        "   пропущенной анкете\n\n"
        "🚀 <b>Буст анкеты</b> — ваша анкета показывается\n"
        "   выше остальных в течение 24 часов\n\n"
        "⭐ <b>Значок Premium</b> на вашей анкете\n\n"
    )

    # Если передан пользователь и у него есть активная подписка
    if user and user.has_premium and user.premium_until:
        from datetime import datetime
        now = datetime.now(user.premium_until.tzinfo)
        if user.premium_until > now:
            days_left = (user.premium_until - now).days
            text += f"📅 <b>Ваша подписка активна до:</b> {user.premium_until.strftime('%d.%m.%Y')}\n"
            text += f"⏰ <b>Осталось дней:</b> {days_left}\n\n"
        else:
            text += "⚠️ <b>Ваша подписка истекла.</b> Продлите её ниже.\n\n"
    else:
        text += "💰 <b>Нет активной подписки.</b> Выберите тариф ниже:\n\n"

    text += "• 1 месяц — 39₽\n"
    text += "• 3 месяца — 105₽\n"
    text += "• 6 месяцев — 200₽\n"
    text += "• 12 месяцев — 350₽\n"

    return text

async def send_media(bot, chat_id: int, user, caption: str, reply_markup=None, parse_mode="HTML"):
    if not user.photos:
        msg = await bot.send_message(
            chat_id=chat_id, text=caption,
            reply_markup=reply_markup, parse_mode=parse_mode,
        )
        return msg

    first = user.photos[0]
    kwargs = dict(chat_id=chat_id, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)

    if getattr(first, "media_type", "photo") == "video":
        msg = await bot.send_video(video=first.file_id, **kwargs)
    else:
        msg = await bot.send_photo(photo=first.file_id, **kwargs)
    return msg