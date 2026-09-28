from app.crud.base import CRUDRepository
from app.models.leave_credits import LeaveCredit
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

class LeaveCreditCRUD(CRUDRepository):
    async def get_by_user_id(self, session: AsyncSession, user_id: int) -> Optional[LeaveCredit]:
        stmt = select(LeaveCredit).where(LeaveCredit.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def create_or_update(self, session: AsyncSession, user_id: int, sick: float = 0, vacation: float = 0) -> LeaveCredit:
        obj = await self.get_by_user_id(session, user_id)
        if obj:
            obj.sick_leave_balance = sick
            obj.vacation_leave_balance = vacation
            session.add(obj)
        else:
            obj = LeaveCredit(user_id=user_id, sick_leave_balance=sick, vacation_leave_balance=vacation)
            session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj

leave_credit_crud = LeaveCreditCRUD(LeaveCredit)
