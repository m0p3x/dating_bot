from datetime import datetime, timedelta, timezone
from typing import Optional, List

from sqlalchemy import select, func, and_, not_, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.models import User, UserTag, Tag, Viewed, Like


class SearchService:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def mark_viewed(self, viewer_id: int, viewed_id: int) -> None:
        result = await self.session.execute(
            select(Viewed).where(
                Viewed.viewer_id == viewer_id,
                Viewed.viewed_id == viewed_id,
            )
        )
        viewed = result.scalar_one_or_none()
        if viewed is None:
            self.session.add(Viewed(viewer_id=viewer_id, viewed_id=viewed_id))
        else:
            viewed.created_at = datetime.now(timezone.utc)
        await self.session.commit()

        from sqlalchemy import update
        await self.session.execute(
            update(User)
            .where(User.id == viewed_id)
            .values(views_count=User.views_count + 1)
        )
        await self.session.commit()

    async def get_next_profile(
            self,
            viewer: User,
            search_gender: Optional[str] = None,
            search_goal: Optional[str] = None,
            search_interests: Optional[List[str]] = None,
            apply_height: bool = False,
            search_height: Optional[int] = None,
    ) -> Optional[User]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.VIEWED_TTL_HOURS)

        viewed_subq = (
            select(Viewed.viewed_id)
            .where(
                Viewed.viewer_id == viewer.id,
                Viewed.created_at >= cutoff,
            )
            .scalar_subquery()
        )

        sent_likes_no_reply = (
            select(Like.to_id)
            .where(
                Like.from_id == viewer.id,
                Like.is_mutual == False,
                Like.is_viewed == False,
            )
            .scalar_subquery()
        )

        received_likes_no_reply = (
            select(Like.from_id)
            .where(
                Like.to_id == viewer.id,
                Like.is_mutual == False,
                Like.is_viewed == False,
            )
            .scalar_subquery()
        )

        # ✅ БАЗОВЫЕ УСЛОВИЯ (всегда)
        base_conditions = [
            User.id != viewer.id,
            User.is_active.is_(True),
            User.is_banned.is_(False),
            not_(User.id.in_(viewed_subq)),
            not_(User.id.in_(sent_likes_no_reply)),
            not_(User.id.in_(received_likes_no_reply)),
        ]

        # ✅ ЖЁСТКИЙ ФИЛЬТР ПО ПОЛУ (никогда не убираем, если выбран)
        if search_gender is not None:
            gender_condition = (User.gender == search_gender)
        else:
            gender_condition = None

        # Дополнительные фильтры
        if not viewer.city:
            return None

        city_condition = (func.lower(User.city) == viewer.city.lower())

        age_min = viewer.age - settings.AGE_FILTER_RANGE
        age_max = viewer.age + settings.AGE_FILTER_RANGE
        age_condition = and_(User.age >= age_min, User.age <= age_max)

        height_condition = None
        if apply_height and search_height:
            r = settings.HEIGHT_FILTER_RANGE
            height_condition = and_(
                User.height.isnot(None),
                User.height >= search_height - r,
                User.height <= search_height + r,
            )

        goal_condition = None
        if search_goal:
            goal_condition = (User.goal == search_goal)

        interests_condition = None
        if search_interests:
            interests_condition = exists(
                select(UserTag.user_id)
                .join(Tag, Tag.id == UserTag.tag_id)
                .where(
                    UserTag.user_id == User.id,
                    Tag.name.in_(search_interests),
                )
            )

        def opt(c):
            return [c] if c is not None else []

        # ✅ ФУНКЦИЯ ПОИСКА (пол добавляется всегда, если выбран)
        async def _try_search(extra_filters: list) -> Optional[User]:
            conditions = base_conditions.copy()

            if gender_condition is not None:
                conditions.append(gender_condition)

            conditions.extend(extra_filters)
            return await self._query_one(conditions)

        # Попытка 1: все фильтры
        candidate = await _try_search(
            opt(city_condition) + [age_condition]
            + opt(height_condition) + opt(goal_condition) + opt(interests_condition)
        )
        if candidate:
            return candidate

        # Попытка 2: без роста
        candidate = await _try_search(
            opt(city_condition) + [age_condition]
            + opt(goal_condition) + opt(interests_condition)
        )
        if candidate:
            return candidate

        # Попытка 3: без цели
        candidate = await _try_search(
            opt(city_condition) + [age_condition]
            + opt(interests_condition)
        )
        if candidate:
            return candidate

        # Попытка 4: без интересов
        candidate = await _try_search(
            opt(city_condition) + [age_condition]
        )
        if candidate:
            return candidate

        # Попытка 5: только город + пол
        candidate = await _try_search(
            opt(city_condition)
        )
        if candidate:
            return candidate

        # ❌ Анкет в городе с выбранным полом нет
        return None

    async def _query_one(self, conditions: list) -> Optional[User]:
        stmt = (
            select(User)
            .where(and_(*conditions))
            .options(
                selectinload(User.photos),
                selectinload(User.tags).selectinload(UserTag.tag),
            )
            .order_by(
                User.is_boosted.desc(),
                func.random(),
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()