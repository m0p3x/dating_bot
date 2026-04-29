from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from typing import List


GOALS = {
    "night": "Провести ночь 🔞",
    "relationship": "Отношения 🥰",
    "friendship": "Дружба 🤝",
}

INTERESTS_LIST = [
    "юмор", "музыка", "игры", "путешествия",
    "спорт", "кино", "книги", "кулинария", "искусство", "технологии",
    "прогулки", "животные", "sex",
]


def skip_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Пропустить")]],
        resize_keyboard=True, one_time_keyboard=True,
    )


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def gender_kb(skip: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Мужской", callback_data="gender:M")
    builder.button(text="👩 Женский", callback_data="gender:F")
    builder.adjust(2)
    if skip:
        builder.row(InlineKeyboardButton(text="Пропустить", callback_data="skip"))
    return builder.as_markup()


def goal_kb(skip: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, label in GOALS.items():
        builder.button(text=label, callback_data=f"goal:{key}")
    builder.adjust(1)
    if skip:
        builder.row(InlineKeyboardButton(text="Пропустить", callback_data="skip"))
    return builder.as_markup()


def interests_kb(selected: List[str], skip: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for interest in INTERESTS_LIST:
        mark = "✅ " if interest in selected else ""
        builder.button(text=f"{mark}{interest}", callback_data=f"interest:{interest}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="✔️ Готово", callback_data="interests_done"))
    if skip:
        builder.row(InlineKeyboardButton(text="Пропустить", callback_data="skip"))
    return builder.as_markup()

def like_response_kb(like_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[])

def main_menu_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="👍 Лайк")
    builder.button(text="⏭ Пропуск")
    builder.button(text="🔍 Смотреть анкеты")
    builder.button(text="❤️ Кто меня лайкнул")
    builder.button(text="👤 Мой профиль")
    builder.adjust(2, 1, 2)
    return builder.as_markup(resize_keyboard=True)

def profile_only_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔍 Смотреть анкеты")
    builder.button(text="❤️ Кто меня лайкнул")
    builder.button(text="👤 Мой профиль")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def search_gender_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Парни", callback_data="search_gender:M")
    builder.button(text="👩 Девушки", callback_data="search_gender:F")
    builder.button(text="👥 Все", callback_data="search_gender:any")
    builder.adjust(3)
    return builder.as_markup()


def search_goal_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, label in GOALS.items():
        builder.button(text=label, callback_data=f"search_goal:{key}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="Пропустить", callback_data="search_skip:goal"))
    return builder.as_markup()


def search_interests_kb(selected: List[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for interest in INTERESTS_LIST:
        mark = "✅ " if interest in selected else ""
        builder.button(text=f"{mark}{interest}", callback_data=f"search_interest:{interest}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="✔️ Готово", callback_data="search_interests_done"))
    builder.row(InlineKeyboardButton(text="Пропустить", callback_data="search_skip:interests"))
    return builder.as_markup()

def profile_preview_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Редактировать анкету", callback_data="profile:edit")
    builder.button(text="🔄 Создать анкету заново", callback_data="profile:recreate")
    builder.adjust(1)
    return builder.as_markup()


def change_filters_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔧 Изменить фильтры", callback_data="browse:change_filters")
    return builder.as_markup()

def browse_kb(has_premium: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Суперлайк", callback_data="browse:super")
    builder.button(text="💬 Сообщение", callback_data="browse:message")
    builder.button(text="🚩 Жалоба", callback_data="browse:report")
    builder.button(text="🔧 Изменить фильтры", callback_data="browse:change_filters")
    builder.adjust(2, 2)
    return builder.as_markup()


def like_received_kb(like_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❤️ Посмотреть", callback_data=f"like_view:{like_id}"),
    ]])

def city_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Отправить мой город (только с телефона)", request_location=True)],
        ],
        resize_keyboard=True, one_time_keyboard=True,
    )

def search_height_skip_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустить", callback_data="search_skip:height")
    builder.adjust(1)
    return builder.as_markup()

def skipped_kb(profile_id: int, has_premium: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_premium:
        builder.button(
            text="↩ Вернуться к анкете",
            callback_data=f"browse:return:{profile_id}",
        )
    else:
        builder.button(
            text="↩ Вернуться к анкете 🔒",
            callback_data="premium:back",
        )
    return builder.as_markup()

def report_reason_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Реклама / спам", callback_data="report_reason:spam")
    builder.button(text="🤬 Оскорбительный контент", callback_data="report_reason:offensive")
    builder.button(text="🎭 Фейковый профиль", callback_data="report_reason:fake")
    builder.button(text="💬 Другое", callback_data="report_reason:other")
    builder.adjust(1)
    return builder.as_markup()

def photo_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Готово")],
            [KeyboardButton(text="Пропустить")],
        ],
        resize_keyboard=True, one_time_keyboard=True,
    )

def back_only_kb(has_premium: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="↩ Вернуться к этой анкете" if has_premium else "↩ Вернуться (🔒)",
        callback_data="browse:back" if has_premium else "premium:back",
    )
    return builder.as_markup()

def profile_kb(has_premium: bool, is_active: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👁 Моя анкета", callback_data="profile:preview")
    builder.button(text="📊 Моя статистика", callback_data="profile:stats")
    builder.button(text="🏆 Топ 5 анкет", callback_data="profile:top5")
    builder.button(text="🔗 Реферальная ссылка", callback_data="profile:referral")  # добавь
    builder.adjust(1)
    if has_premium:
        builder.button(text="🚀 Буст анкеты", callback_data="profile:boost")
    else:
        builder.button(text="🚀 Буст анкеты 🔒", callback_data="premium:boost")
    builder.adjust(1)
    builder.button(text="⭐ Подписка", callback_data="profile:subscription")
    pause_text = "▶️ Активировать анкету" if not is_active else "⏸ Приостановить анкету"
    builder.button(text=pause_text, callback_data="profile:pause")
    builder.button(text="🗑 Удалить анкету", callback_data="profile:delete")
    builder.adjust(1)
    return builder.as_markup()

def confirm_delete_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить", callback_data="profile:delete_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="profile:delete_cancel"),
    ]])


def subscription_kb(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💳 Оформить за 39 ₽/мес", url=url),
    ]])


def admin_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Жалобы", callback_data="admin:reports")
    builder.button(text="👥 Пользователи", callback_data="admin:users")
    builder.button(text="📊 Статистика", callback_data="admin:stats")
    builder.button(text="📢 Рассылка", callback_data="admin:broadcast")
    builder.adjust(2)
    return builder.as_markup()


def admin_report_kb(report_id: int, user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⚠️ Предупредить", callback_data=f"admin_report:warn:{report_id}:{user_id}")
    builder.button(text="🔇 Временный бан (7д)", callback_data=f"admin_report:ban_temp:{report_id}:{user_id}")
    builder.button(text="🚫 Постоянный бан", callback_data=f"admin_report:ban_perm:{report_id}:{user_id}")
    builder.button(text="🗑 Удалить анкету", callback_data=f"admin_report:delete_profile:{report_id}:{user_id}")
    builder.button(text="✅ Отклонить жалобу", callback_data=f"admin_report:dismiss:{report_id}:{user_id}")
    builder.adjust(1)
    return builder.as_markup()


def admin_user_kb(user_id: int, is_banned: bool, has_premium: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_banned:
        builder.button(text="✅ Разбанить", callback_data=f"admin_user:unban:{user_id}")
    else:
        builder.button(text="🚫 Забанить", callback_data=f"admin_user:ban:{user_id}")
    if has_premium:
        builder.button(text="⭐ Снять подписку", callback_data=f"admin_user:remove_premium:{user_id}")
    else:
        builder.button(text="⭐ Выдать подписку", callback_data=f"admin_user:give_premium:{user_id}")
    builder.button(text="🗑 Удалить анкету", callback_data=f"admin_user:delete:{user_id}")
    builder.adjust(1)
    return builder.as_markup()
