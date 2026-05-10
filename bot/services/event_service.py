from typing import Optional, List
from datetime import date
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models import Event, EventCategory
from sqlalchemy.orm import selectinload

class EventService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_categories(self):
        result = await self.session.execute(select(EventCategory))
        return result.scalars().all()

    async def get_category_by_id(self, category_id: int):
        result = await self.session.execute(select(EventCategory).where(EventCategory.id == category_id))
        return result.scalar_one_or_none()

    async def get_user_active_event(self, user_id: int) -> Optional[Event]:
        today = date.today()
        result = await self.session.execute(
            select(Event)
            .where(
                Event.creator_id == user_id,
                Event.is_active == True,
                Event.event_date >= today
            )
            .options(selectinload(Event.creator))
        )
        return result.scalar_one_or_none()

    async def create_event(self, creator_id: int, category_id: int, city: str, event_date: date, description: str) -> Event:
        event = Event(
            creator_id=creator_id,
            category_id=category_id,
            city=city,
            event_date=event_date,
            description=description,
            is_active=True
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def get_events_by_category(self, category_id: int, city: str) -> List[Event]:
        today = date.today()
        result = await self.session.execute(
            select(Event)
            .where(
                Event.category_id == category_id,
                Event.city == city,
                Event.is_active == True,
                Event.event_date >= today
            )
            .options(selectinload(Event.creator))  # ← добавить
            .order_by(Event.event_date)
        )
        return result.scalars().all()

    async def get_event_by_id(self, event_id: int) -> Optional[Event]:
        result = await self.session.execute(
            select(Event)
            .where(Event.id == event_id)
            .options(selectinload(Event.creator))  # ← явно загружаем создателя
        )
        return result.scalar_one_or_none()

    async def deactivate_expired_events(self):
        today = date.today()
        await self.session.execute(
            update(Event)
            .where(Event.is_active == True, Event.event_date < today)
            .values(is_active=False)
        )
        await self.session.commit()