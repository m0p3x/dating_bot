from datetime import date
from typing import Optional, List
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.models import Like, User, UserTag
from bot.keyboards import like_received_kb
from bot.utils.formatters import format_profile


class MatchService:

    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot

    async def can_send_message_like(self, user: User) -> bool:
        if user.has_premium:
            return True
        today = date.today()
        if user.msg_like_date != today:
            return True
        return user.msg_like_count < settings.MSG_LIKE_DAILY_LIMIT

    async def can_send_super_like(self, user: User) -> bool:
        if user.has_premium:
            return True
        today = date.today()
        return user.super_like_date != today

    async def _increment_message_like(self, user: User) -> None:
        today = date.today()
        if user.msg_like_date != today:
            user.msg_like_count = 1
            user.msg_like_date = today
        else:
            user.msg_like_count += 1
        await self.session.commit()

    async def _mark_super_like_used(self, user: User) -> None:
        user.super_like_date = date.today()
        await self.session.commit()

    async def send_like(
            self,
            from_user: User,
            to_user: User,
            like_type: str,
            message: Optional[str] = None,
    ) -> Optional[Like]:
        print(f"send_like: from={from_user.id} to={to_user.id}, type={like_type}")

        if from_user.id == to_user.id:
            return None

        if like_type == "message" and not await self.can_send_message_like(from_user):
            return None
        if like_type == "super" and not await self.can_send_super_like(from_user):
            return None

        existing_like = await self.session.execute(
            select(Like)
            .where(
                Like.from_id == to_user.id,
                Like.to_id == from_user.id,
            )
            .options(
                selectinload(Like.from_user).selectinload(User.photos),
                selectinload(Like.from_user).selectinload(User.tags).selectinload(UserTag.tag),
            )
            .limit(1)
        )
        existing = existing_like.scalar_one_or_none()

        like = Like(
            from_id=from_user.id,
            to_id=to_user.id,
            type=like_type,
            message=message,
            is_mutual=False,
        )
        self.session.add(like)
        await self.session.flush()

        if existing:
            existing.is_mutual = True
            like.is_mutual = True
            await self.session.commit()
            await self._notify_match(from_user, to_user)
            return like

        if like_type == "message":
            await self._increment_message_like(from_user)
        if like_type == "super":
            await self._mark_super_like_used(from_user)

        await self.session.commit()
        await self.session.refresh(like)
        await self._notify_receiver(like, from_user, to_user)

        return like

    async def reply_like(self, like_id: int, replying_user: User) -> bool:
        result = await self.session.execute(
            select(Like)
            .where(Like.id == like_id, Like.to_id == replying_user.id)
            .options(
                selectinload(Like.from_user).selectinload(User.photos),
                selectinload(Like.from_user).selectinload(User.tags).selectinload(UserTag.tag),
            )
        )
        original_like = result.scalar_one_or_none()

        if original_like is None:
            return False

        from_user = original_like.from_user
        from_user_id = from_user.id
        replying_user_id = replying_user.id

        original_like.is_mutual = True

        reverse_like = await self.session.execute(
            select(Like).where(
                Like.from_id == replying_user_id,
                Like.to_id == from_user_id,
            )
        )
        reverse = reverse_like.scalar_one_or_none()
        if reverse:
            reverse.is_mutual = True

        await self.session.commit()
        await self._notify_match(from_user, replying_user)

        return True

    async def get_incoming_likes(self, user_id: int) -> List[Like]:
        result = await self.session.execute(
            select(Like)
            .where(
                Like.to_id == user_id,
                Like.is_mutual == False,
                Like.is_viewed == False,
            )
            .options(
                selectinload(Like.from_user).selectinload(User.photos),
                selectinload(Like.from_user).selectinload(User.tags).selectinload(UserTag.tag),
            )
            .order_by(
                (Like.type == "super").desc(),
                Like.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def mark_like_viewed(self, like_id: int) -> None:
        result = await self.session.execute(select(Like).where(Like.id == like_id))
        like = result.scalar_one_or_none()
        if like:
            like.is_viewed = True
            await self.session.commit()

    async def _notify_receiver(self, like: Like, from_user: User, to_user: User) -> None:
        try:
            if like.type == "message":
                text = (
                    "💬 <b>Вам написали сообщение!</b>\n\n"
                    "Кто-то хочет познакомиться с вами и отправил сообщение. Посмотреть?"
                )
            elif like.type == "super":
                text = "⭐ <b>Кто-то поставил вам суперлайк!</b>\nПосмотреть анкету?"
            else:
                text = "❤️ <b>Кто-то оценил вашу анкету!</b>\nПосмотреть? Или посмотрите позже в разделе «Кто меня лайкнул»"

            await self.bot.send_message(
                chat_id=to_user.tg_id,
                text=text,
                reply_markup=like_received_kb(like.id),
                parse_mode="HTML",
            )
        except Exception:
            pass

    async def _notify_match(self, user1: User, user2: User) -> None:
        for sender, receiver in [(user1, user2), (user2, user1)]:
            text = format_profile(receiver)
            text += "\n\n🎉 <b>У вас взаимная симпатия!</b>\n\n"

            if receiver.username:
                text += f"👤 <b>Контакт:</b> @{receiver.username}"
            else:
                text += f"👤 <b>Контакт:</b> <a href='tg://user?id={receiver.tg_id}'>нажмите для связи</a>"

            try:
                if receiver.photos and len(receiver.photos) > 0:
                    first = receiver.photos[0]
                    if getattr(first, "media_type", "photo") == "video":
                        await self.bot.send_video(
                            chat_id=sender.tg_id,
                            video=first.file_id,
                            caption=text,
                            parse_mode="HTML",
                        )
                    else:
                        await self.bot.send_photo(
                            chat_id=sender.tg_id,
                            photo=first.file_id,
                            caption=text,
                            parse_mode="HTML",
                        )
                else:
                    await self.bot.send_message(
                        chat_id=sender.tg_id,
                        text=text,
                        parse_mode="HTML",
                    )
            except Exception:
                await self.bot.send_message(
                    chat_id=sender.tg_id,
                    text=text,
                    parse_mode="HTML",
                )
