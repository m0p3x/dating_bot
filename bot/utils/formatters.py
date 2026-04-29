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


def format_subscription_info() -> str:
    """Экран описания подписки."""
    return (
        "⭐ <b>Подписка за 39 ₽/мес</b>\n\n"
        "С подпиской вы получаете:\n\n"
        "💬 <b>Сообщение</b> — без ограничений\n"
        "   (бесплатно: 3 в день)\n\n"
        "⭐ <b>Суперлайк (тот же лайк, но для особо понравившихся)</b> — без ограничений\n"
        "   (бесплатно: 1 в день)\n\n"
        "↩ <b>Возврат к анкете</b> — вернитесь к случайно\n"
        "   пропущенной анкете\n\n"
        "🚀 <b>Буст анкеты</b> — ваша анкета показывается\n"
        "   выше остальных в течение 24 часов\n\n"
        "⭐ <b>Значок Premium</b> на вашей анкете\n"
    )

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