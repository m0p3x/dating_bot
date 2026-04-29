from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models import Report, User


class ReportService:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        from_id: int,
        to_id: int,
        reason: str,
        comment: Optional[str] = None,
    ) -> Report:
        report = Report(
            from_id=from_id,
            to_id=to_id,
            reason=reason,
            comment=comment,
            status="pending",
        )
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def get_pending(self) -> List[Report]:
        result = await self.session.execute(
            select(Report)
            .where(Report.status == "pending")
            .options(selectinload(Report.reported_user))
            .order_by(Report.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, report_id: int) -> Optional[Report]:
        result = await self.session.execute(
            select(Report)
            .where(Report.id == report_id)
            .options(selectinload(Report.reported_user))
        )
        return result.scalar_one_or_none()

    async def resolve(self, report_id: int) -> None:
        report = await self.get_by_id(report_id)
        if report:
            report.status = "resolved"
            await self.session.commit()

    async def dismiss(self, report_id: int) -> None:
        report = await self.get_by_id(report_id)
        if report:
            report.status = "dismissed"
            await self.session.commit()

    async def pending_count(self) -> int:
        result = await self.session.execute(
            select(func.count()).where(Report.status == "pending")
        )
        return result.scalar_one()
