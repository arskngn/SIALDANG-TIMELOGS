from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_async_session
from app.models.users import User
from app.models.leave_credits import LeaveCredit
from app.schemas.leave_credits import LeaveCreditResponse, LeaveCreditUpdate
from app.crud.leave_credits import leave_credit_crud
from app.api.dependencies import get_current_user, get_current_admin
from app.utils.user_utils import is_user_account_active
from datetime import datetime
from typing import List

router = APIRouter(prefix="/leave-credits", tags=["Leave Credits"])

@router.get("/my-credits", response_model=LeaveCreditResponse)
async def get_my_credits(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    """Get current user's leave credits. Creates if not exists."""
    today = datetime.now().date()
    current_month = today.strftime("%Y-%m")

    credit = await leave_credit_crud.get_by_user_id(session, user.id)
    if not credit:
        credit = LeaveCredit(user_id=user.id, sick_leave_balance=0, vacation_leave_balance=0)
        session.add(credit)

    if is_user_account_active(user.emp_start_date, user.emp_end_date, today):
        if credit.last_allocation_month != current_month:
            credit.sick_leave_balance += 1
            credit.vacation_leave_balance += 1
            credit.last_allocation_month = current_month
            session.add(credit)

    await session.commit()
    await session.refresh(credit)
    return credit

@router.get("/user/{user_id}", response_model=LeaveCreditResponse)
async def get_user_credits(
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user) # Allow any user to see? Or just admin/manager? User requested "display the user sick leave... in user profile", assuming self or authorized viewer.
):
    user_orm = await session.get(User, user_id)
    if not user_orm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    today = datetime.now().date()
    current_month = today.strftime("%Y-%m")

    credit = await leave_credit_crud.get_by_user_id(session, user_id)
    if not credit:
        credit = LeaveCredit(user_id=user_id, sick_leave_balance=0, vacation_leave_balance=0)
        session.add(credit)

    if is_user_account_active(user_orm.emp_start_date, user_orm.emp_end_date, today):
        if credit.last_allocation_month != current_month:
            credit.sick_leave_balance += 1
            credit.vacation_leave_balance += 1
            credit.last_allocation_month = current_month
            session.add(credit)

    await session.commit()
    await session.refresh(credit)
    return credit

@router.post("/allocate-monthly")
async def allocate_monthly_credits(
    session: AsyncSession = Depends(get_async_session),
    admin: User = Depends(get_current_admin)
):
    """
    Manually trigger monthly allocation (1 sick, 1 vacation) for all users.
    Checks if already allocated for current month to avoid duplicates.
    """
    current_month = datetime.now().strftime("%Y-%m")
    
    # Get all users
    result = await session.execute(select(User).where(User.blocked == False)) # Only unblocked users
    users = result.scalars().all()
    
    count = 0
    for u in users:
        # Skip users whose contract has not started or has ended
        if not is_user_account_active(u.emp_start_date, u.emp_end_date):
            continue

        credit = await leave_credit_crud.get_by_user_id(session, u.id)
        if not credit:
            credit = LeaveCredit(user_id=u.id, sick_leave_balance=0, vacation_leave_balance=0)
            session.add(credit)
        
        # Check if already allocated this month
        if credit.last_allocation_month != current_month:
            credit.sick_leave_balance += 1
            credit.vacation_leave_balance += 1
            credit.last_allocation_month = current_month
            session.add(credit)
            count += 1
            
    await session.commit()
    return {"message": f"Allocated credits for {count} users for {current_month}"}

@router.post("/reset-yearly")
async def reset_yearly_credits(
    session: AsyncSession = Depends(get_async_session),
    admin: User = Depends(get_current_admin)
):
    """
    Reset all leave credits to 0. Should be called at start of year.
    """
    result = await session.execute(select(LeaveCredit))
    credits = result.scalars().all()
    
    for c in credits:
        c.sick_leave_balance = 0
        c.vacation_leave_balance = 0
        c.last_allocation_month = None # Reset allocation tracking? Or keep it? Maybe keep it.
        session.add(c)
        
    await session.commit()
    return {"message": f"Reset credits for {len(credits)} users"}

@router.put("/user/{user_id}", response_model=LeaveCreditResponse)
async def update_user_credits(
    user_id: int,
    update_data: LeaveCreditUpdate,
    session: AsyncSession = Depends(get_async_session),
    admin: User = Depends(get_current_admin)
):
    """Admin update of user credits"""
    credit = await leave_credit_crud.get_by_user_id(session, user_id)
    if not credit:
        credit = LeaveCredit(user_id=user_id)
        session.add(credit)
    
    if update_data.sick_leave_balance is not None:
        credit.sick_leave_balance = update_data.sick_leave_balance
    if update_data.vacation_leave_balance is not None:
        credit.vacation_leave_balance = update_data.vacation_leave_balance
    if update_data.last_allocation_month is not None:
        credit.last_allocation_month = update_data.last_allocation_month
        
    await session.commit()
    await session.refresh(credit)
    return credit
