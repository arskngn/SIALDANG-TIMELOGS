from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
from app.secrets import DEFAULT_TIMEZONE
from app.database import get_async_session
from app.api.dependencies import get_current_user, get_current_admin, get_current_manager
from app.models.timelogs import Timelog
from app.schemas.timelogs import CreateTimelog, UpdateTimelog, TimelogResponse, DuplicateTimelog, DuplicateTimelogToDates, UpdateTimelogStatus
from app.crud.timelogs import timelog_crud
from app.models.users import User
from app.models.projects import Project
from app.models.user_projects import UserProject
from app.models.approvals import Approval
from app.models.notifications import Notification
from app.models.task_types import TaskType
from app.models.leave_credits import LeaveCredit
from app.crud.leave_credits import leave_credit_crud


router = APIRouter(
    prefix="/timelog",
    tags=["Timelogs"],
    responses={404: {"description": "Not found"}},
)


# ============================================================================
# HELPER FUNCTIONS FOR ROLE-BASED ACCESS CONTROL
# ============================================================================

async def can_user_approve_timelog(
    user: User,
    timelog: Timelog,
    session: AsyncSession,
) -> bool:
    """
    Check if a user can manage/approve/reject a timelog.
    
    Access rules:
    - Admin: Can manage all timelogs
    - Project Manager assignment: Can manage timelogs of other users in their assigned projects
    - Regular User: Cannot manage any timelogs
    - Users cannot approve/reject their own timelogs
    """
    user_role = (user.role or "").lower()
    
    # Admin can manage all timelogs, including their own
    if user_role == "admin":
        return True
    
    # Users cannot approve/reject their own timelogs
    if timelog.user_id == user.id:
        return False
    
    # Get projects where user is assigned as project manager
    proj_mgr_query = select(UserProject.project_id).where(
        UserProject.user_id == user.id,
        func.lower(UserProject.role_in_project) == "project_manager",
    )
    proj_mgr_result = await session.execute(proj_mgr_query)
    managed_projects = [row[0] for row in proj_mgr_result.all()]
    
    if not managed_projects:
        # Not a project manager assignment, cannot manage
        return False
    
    # Project managers can manage tasks for:
    # 1. Tasks in their managed projects
    # 2. Tasks assigned to users in their managed projects
    if timelog.project_id and timelog.project_id in managed_projects:
        return True
    
    # Also check if the timelog belongs to a user in one of their managed projects
    if timelog.user_id:
        user_in_project = await session.execute(
            select(UserProject.project_id).where(
                UserProject.user_id == timelog.user_id,
                UserProject.project_id.in_(managed_projects)
            )
        )
        if user_in_project.first():
            return True
    
    return False


async def get_user_managed_projects(
    user: User,
    session: AsyncSession,
) -> Tuple[List[int], bool]:
    """
    Get list of project IDs where user is assigned as project manager.
    
    Returns:
        Tuple[List[int], bool]: (project_ids, is_admin)
    """
    user_role = (user.role or "").lower()
    is_admin = user_role == "admin"
    
    if is_admin:
        # Admin has access to all projects
        all_projects = await session.execute(select(Project.id))
        return [row[0] for row in all_projects.all()], True
    
    # Get projects where user is assigned as project manager
    assigned = await session.execute(
        select(UserProject.project_id).where(
            UserProject.user_id == user.id,
            func.lower(UserProject.role_in_project) == "project_manager",
        )
    )
    project_ids = [row[0] for row in assigned.all()]
    
    return project_ids, False



@router.get("/", response_model=List[TimelogResponse])
async def list_my_timelogs(session: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_user)):
    # CRITICAL: Always filter by user_id for security - regular users can ONLY see their own timelogs
    #print(f"DEBUG: list_my_timelogs called for user_id={user.id}, username={user.username}, role={user.role}")
    timelog_list: List[Timelog] = await timelog_crud.get_many(session, Timelog.user_id == user.id)
    #print(f"DEBUG: Returning {len(timelog_list)} timelogs for user {user.id}")
    # Add user info for each timelog (in this case, it's always the current user)
    # Build approver map
    approver_ids = {t.approver_id for t in timelog_list if getattr(t, "approver_id", None)}
    approver_map: Dict[int, str] = {}
    if approver_ids:
        res = await session.execute(select(User.id, User.username, User.first_name, User.last_name).where(User.id.in_(approver_ids)))
        for uid, uname, fname, lname in res.all():
            name = f"{fname or ''} {lname or ''}".strip() or uname
            approver_map[uid] = name
    timelog_ids = [t.id for t in timelog_list]
    fallback_approver_by_timelog: Dict[int, int] = {}
    if timelog_ids:
        latest_notifs_subq = (
            select(
                Notification.item_id.label("item_id"),
                func.max(Notification.created_at).label("latest_created_at"),
            )
            .where(
                Notification.item_type == "timelog",
                Notification.item_id.in_(timelog_ids),
                Notification.action.in_(["approved", "rejected"]),
            )
            .group_by(Notification.item_id)
            .subquery()
        )
        notif_res = await session.execute(
            select(Notification.item_id, Notification.approver_id)
            .join(
                latest_notifs_subq,
                (Notification.item_id == latest_notifs_subq.c.item_id)
                & (Notification.created_at == latest_notifs_subq.c.latest_created_at),
            )
            .where(
                Notification.item_type == "timelog",
                Notification.action.in_(["approved", "rejected"]),
            )
        )
        for tlid, appr_id in notif_res.all():
            if tlid not in fallback_approver_by_timelog:
                fallback_approver_by_timelog[tlid] = appr_id
    fallback_names: Dict[int, str] = {}
    if fallback_approver_by_timelog:
        uniq_fallback_ids = list(set(fallback_approver_by_timelog.values()))
        res2 = await session.execute(
            select(User.id, User.username, User.first_name, User.last_name).where(User.id.in_(uniq_fallback_ids))
        )
        for uid, uname, fname, lname in res2.all():
            fallback_names[uid] = (f"{fname or ''} {lname or ''}".strip() or uname)
    return [
        TimelogResponse.model_validate(t, from_attributes=True).model_copy(
            update={
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "approver_id": getattr(t, "approver_id", None),
                "approved_at": getattr(t, "approved_at", None),
                "approver_name": (
                    approver_map.get(getattr(t, "approver_id", None))
                    or fallback_names.get(fallback_approver_by_timelog.get(t.id, -1))
                ),
            }
        )
        for t in timelog_list
    ]


@router.get("/all", response_model=List[TimelogResponse])
async def list_all_timelogs(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """
    List all timelogs accessible to the current user based on their role and assignments.
    
    - Admin: See all timelogs
    - Project Manager: See timelogs of all users in their assigned projects + their own
    - User: Can only see their own timelogs
    """
    user_role = (user.role or "").lower()
    #print(f"DEBUG /all endpoint: user_id={user.id}, username={user.username}, role={user_role}")
    
    # Check if user is assigned as a project manager
    proj_mgr_query = select(UserProject.project_id).where(
        UserProject.user_id == user.id,
        func.lower(UserProject.role_in_project) == "project_manager",
    )
    proj_mgr_result = await session.execute(proj_mgr_query)
    managed_project_ids = [row[0] for row in proj_mgr_result.all()]
    #print(f"DEBUG /all: managed_project_ids={managed_project_ids}")
    
    if user_role == "admin":
        # Admin sees all timelogs
        #print(f"DEBUG /all: User is admin, returning all timelogs")
        timelog_list = await timelog_crud.get_many(session)
    elif managed_project_ids:
        # Project manager sees:
        # 1. All timelogs for tasks in their managed projects
        # 2. All timelogs from users assigned to their managed projects
        # 3. Their own timelogs
        #print(f"DEBUG /all: User is project manager for {len(managed_project_ids)} projects")
        
        # Get users assigned to managed projects
        users_in_projects = await session.execute(
            select(UserProject.user_id).where(
                UserProject.project_id.in_(managed_project_ids)
            )
        )
        managed_user_ids = {row[0] for row in users_in_projects.all()}
        managed_user_ids.add(user.id)  # Also add their own
        #print(f"DEBUG /all: managed_user_ids={managed_user_ids}")
        
        # Get timelogs from managed users OR in managed projects
        if managed_user_ids:
            timelog_list = await timelog_crud.get_many(
                session,
                or_(
                    Timelog.user_id.in_(managed_user_ids),
                    Timelog.project_id.in_(managed_project_ids)
                )
            )
        else:
            timelog_list = []
    else:
        # Regular users see only their own timelogs
        #print(f"DEBUG /all: User is regular user, returning only their own timelogs")
        timelog_list = await timelog_crud.get_many(session, Timelog.user_id == user.id)
    
    #print(f"DEBUG /all: Returning {len(timelog_list)} timelogs")
    
    # Fetch all user info for timelogs
    user_ids = set(t.user_id for t in timelog_list if t.user_id)
    approver_ids = set(t.approver_id for t in timelog_list if getattr(t, "approver_id", None))
    user_id_map: Dict[int, Dict[str, str]] = {}
    if user_ids:
        user_res = await session.execute(
            select(User.id, User.username, User.first_name, User.last_name).where(User.id.in_(user_ids))
        )
        user_id_map = {uid: {"username": uname, "first_name": fname, "last_name": lname} for uid, uname, fname, lname in user_res.all()}
    approver_map: Dict[int, str] = {}
    if approver_ids:
        appr_res = await session.execute(
            select(User.id, User.username, User.first_name, User.last_name).where(User.id.in_(approver_ids))
        )
        for uid, uname, fname, lname in appr_res.all():
            approver_map[uid] = (f"{fname or ''} {lname or ''}".strip() or uname)
    timelog_ids = [t.id for t in timelog_list]
    fallback_approver_by_timelog: Dict[int, int] = {}
    if timelog_ids:
        latest_notifs_subq = (
            select(
                Notification.item_id.label("item_id"),
                func.max(Notification.created_at).label("latest_created_at"),
            )
            .where(
                Notification.item_type == "timelog",
                Notification.item_id.in_(timelog_ids),
                Notification.action.in_(["approved", "rejected"]),
            )
            .group_by(Notification.item_id)
            .subquery()
        )
        notif2_res = await session.execute(
            select(Notification.item_id, Notification.approver_id)
            .join(
                latest_notifs_subq,
                (Notification.item_id == latest_notifs_subq.c.item_id)
                & (Notification.created_at == latest_notifs_subq.c.latest_created_at),
            )
            .where(
                Notification.item_type == "timelog",
                Notification.action.in_(["approved", "rejected"]),
            )
        )
        for tlid, appr_id in notif2_res.all():
            if tlid not in fallback_approver_by_timelog:
                fallback_approver_by_timelog[tlid] = appr_id
    fallback_names: Dict[int, str] = {}
    if fallback_approver_by_timelog:
        uniq_ids = list(set(fallback_approver_by_timelog.values()))
        res3 = await session.execute(
            select(User.id, User.username, User.first_name, User.last_name).where(User.id.in_(uniq_ids))
        )
        for uid, uname, fname, lname in res3.all():
            fallback_names[uid] = (f"{fname or ''} {lname or ''}".strip() or uname)
    
    return [
        TimelogResponse.model_validate(t, from_attributes=True).model_copy(
            update={
                "username": user_id_map.get(t.user_id, {}).get("username"),
                "first_name": user_id_map.get(t.user_id, {}).get("first_name"),
                "last_name": user_id_map.get(t.user_id, {}).get("last_name"),
                "approver_id": getattr(t, "approver_id", None),
                "approved_at": getattr(t, "approved_at", None),
                "approver_name": (
                    approver_map.get(getattr(t, "approver_id", None))
                    or fallback_names.get(fallback_approver_by_timelog.get(t.id, -1))
                ),
            }
        )
        for t in timelog_list
    ]


@router.post("/", response_model=TimelogResponse)
async def create_timelog(body: CreateTimelog, session: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_user)):
    def round_down(dt: datetime) -> datetime:
        minutes = (dt.minute // 15) * 15
        return dt.replace(minute=minutes, second=0, microsecond=0)

    def round_up(dt: datetime) -> datetime:
        minutes = ((dt.minute + 14) // 15) * 15
        if minutes == 60:
            dt = dt.replace(hour=dt.hour + 1, minute=0, second=0, microsecond=0)
        else:
            dt = dt.replace(minute=minutes, second=0, microsecond=0)
        return dt

    start = round_down(body.start_time)
    end = round_up(body.end_time)
    if end <= start:
        raise HTTPException(status_code=400, detail="End time must be after start time")

    duration = int((end - start).total_seconds() // 60)
    if duration % 15 != 0:
        # Shouldn't happen due to rounding, but guard anyway
        raise HTTPException(status_code=400, detail="Duration must be multiple of 15 minutes")

    # Enforce contract date range: timelogs can only be created within emp_start_date..emp_end_date
    try:
        if isinstance(user.emp_start_date, date) and isinstance(user.emp_end_date, date):
            start_date_local = start.date()
            end_date_local = end.date()
            if start_date_local < user.emp_start_date or end_date_local > user.emp_end_date:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create timelogs within your contract period."
                )
    except HTTPException:
        raise
    except Exception:
        # Fail-safe: do not block if dates are missing or invalid types
        pass

    # Frontend sends aware datetimes with the browser's local timezone offset.
    # Just strip the tzinfo to store as naive local datetimes in the DB.
    # Do NOT use astimezone() as that converts to another timezone first.
    body.user_id = user.id
    body.start_time = start.replace(tzinfo=None) if start.tzinfo else start
    body.end_time = end.replace(tzinfo=None) if end.tzinfo else end
    body.duration_minutes = duration

    # Prevent overlapping timelogs for the same user
    overlap_result = await session.execute(
        select(Timelog).where(
            Timelog.user_id == user.id,
            Timelog.start_time < body.end_time,
            Timelog.end_time > body.start_time,
        )
    )

    if overlap_result.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="You already have a timelog that overlaps this time period."
        )

    if body.type == "project" and body.project_id:
        # Check if project exists
        p = await session.get(Project, body.project_id)
        if not p:
            raise HTTPException(status_code=400, detail="Project not found")

    # Leave Credit Deduction Logic
    if body.type == "leave" and body.task_type_id:
        # Store the actual duration in DB
        body.duration_minutes = duration

        # Get task type
        tt_res = await session.execute(select(TaskType).where(TaskType.id == body.task_type_id))
        task_type = tt_res.scalars().first()
        
        if task_type:
            tt_name = task_type.name.lower()
            is_sick = "sick" in tt_name
            is_vacation = "vacation" in tt_name
            
            if is_sick or is_vacation:
                # Simple leave credit: 1.0 for full day, 0.5 for half day
                # Full day = 480+ minutes, Half day = 240-420 minutes
                deduction = 0.0
                
                if duration >= 420:  # Full day or close to it (7+ hours)
                    deduction = 1.0
                elif duration >= 210:  # Half day or more (3.5+ hours)
                    deduction = 0.5
                else:
                    deduction = 0.0
                
                credit = await leave_credit_crud.get_by_user_id(session, user.id)
                if not credit:
                    credit = LeaveCredit(user_id=user.id)
                    session.add(credit)
                
                if is_sick:
                    credit.sick_leave_balance -= deduction
                elif is_vacation:
                    credit.vacation_leave_balance -= deduction
                session.add(credit)

    created = await timelog_crud.create(session, body)
    return TimelogResponse.model_validate(created, from_attributes=True)


@router.get("/summary", summary="Weekly summary for current user")
async def weekly_summary(weeks: int = 4, session: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    from zoneinfo import ZoneInfo
    from app.secrets import DEFAULT_TIMEZONE
    try:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    except Exception:
        tz = None
    now_local = datetime.now(tz) if tz else datetime.now()
    today_local = now_local.date()
    days_since_sunday = (today_local.weekday() + 1) % 7
    start_of_week_local = today_local - timedelta(days=days_since_sunday)
    results = []
    for i in range(weeks):
        week_start_local = start_of_week_local - timedelta(days=7 * i)
        week_end_local = week_start_local + timedelta(days=7)

        # DB stores naive datetimes in local timezone; build naive local bounds
        week_start_naive = datetime(week_start_local.year, week_start_local.month, week_start_local.day)
        week_end_naive = datetime(week_end_local.year, week_end_local.month, week_end_local.day)

        stmt = select(Timelog).where(
            Timelog.user_id == user.id,
            Timelog.start_time >= week_start_naive,
            Timelog.end_time < week_end_naive,
        )
        data = await session.execute(stmt)
        items: List[Timelog] = data.scalars().all()
        # Include all types (project, leave, other)
        work_items = items
        def within_contract(d: date) -> bool:
            try:
                if isinstance(user.emp_start_date, date) and isinstance(user.emp_end_date, date):
                    return (d >= user.emp_start_date) and (d <= user.emp_end_date)
            except Exception:
                pass
            return True
        # Include tasks within contract period (including weekends if logged)
        work_items_mf = [
            t for t in work_items
            if within_contract(t.start_time.date())
        ]
        
        total_minutes = sum((t.duration_minutes or 0) for t in work_items_mf)
        pending_minutes = sum((t.duration_minutes or 0) for t in work_items_mf if t.status == "Pending")
        rejected_minutes = sum((t.duration_minutes or 0) for t in work_items_mf if t.status == "Rejected")
        approved_minutes = sum((t.duration_minutes or 0) for t in work_items_mf if t.status == "Approved")
        deficient_minutes = max(0, (40 * 60) - total_minutes)
        results.append({
            "week_start": str(week_start_local),
            "week_end": str((week_end_local - timedelta(days=1))),
            "total_logged_hours": round(total_minutes / 60, 2),
            "deficient_hours": round(deficient_minutes / 60, 2),
            "approved_hours": round(approved_minutes / 60, 2),
            "for_approval_hours": round(pending_minutes / 60, 2),
            "rejected_hours": round(rejected_minutes / 60, 2),
        })
    return results

@router.get("/managed", response_model=List[TimelogResponse])
async def list_managed_timelogs(
    status_filter: str = Query("All"),
    session: AsyncSession = Depends(get_async_session),
    current: User = Depends(get_current_user),  # Changed from get_current_manager to get_current_user
) -> List[TimelogResponse]:
    #print(f"\nDEBUG /timelog/managed called for user_id={current.id}, username={current.username}, role={current.role}, status_filter={repr(status_filter)}")
    
    # Find projects managed directly by current user
    proj_stmt = select(Project.id).where(Project.manager_id == current.id)
    proj_ids_res = await session.execute(proj_stmt)
    proj_ids_direct = [row[0] for row in proj_ids_res.all()]
    #print(f"DEBUG: Direct projects (manager_id): {proj_ids_direct}")
    
    # Find projects where current user is assigned as project manager
    proj_role_stmt = select(UserProject.project_id).where(
        UserProject.user_id == current.id,
        func.lower(UserProject.role_in_project) == "project_manager",
    )
    proj_role_res = await session.execute(proj_role_stmt)
    proj_ids_role = [row[0] for row in proj_role_res.all()]
    #print(f"DEBUG: Projects from user_projects (role_in_project): {proj_ids_role}")
    
    proj_ids = list({*proj_ids_direct, *proj_ids_role})
    #print(f"DEBUG: Combined managed projects: {proj_ids}")
    
    # Check if user is admin - if so, they see everything
    is_admin = (current.role or "").lower() == "admin"
    #print(f"DEBUG: is_admin={is_admin}")
    
    if is_admin:
        #print(f"DEBUG: {current.username} is admin, showing all timelogs")
        proj_conditions = []
        # Get all users for admin
        all_user_stmt = select(UserProject.user_id)
        all_users_res = await session.execute(all_user_stmt)
        user_ids = [row[0] for row in all_users_res.all()]
        user_conditions = [Timelog.user_id.in_(user_ids)] if user_ids else []
    elif not proj_ids:
        #print(f"DEBUG: {current.username} has no managed projects, returning empty")
        return []
    else:
        #print(f"DEBUG: {current.username} manages projects: {proj_ids}")
        proj_conditions = [Timelog.project_id.in_(proj_ids)]
        # Get all users who have timelogs for these projects
        user_stmt = select(Timelog.user_id).where(Timelog.project_id.in_(proj_ids)).distinct()
        user_ids_res = await session.execute(user_stmt)
        user_ids = [row[0] for row in user_ids_res.all()]
        #print(f"DEBUG: Users with timelogs for managed projects: {user_ids}")
        user_conditions = [Timelog.user_id.in_(user_ids)] if user_ids else []
    
    # Handle status filter - only apply if specified and valid
    if status_filter and status_filter != "All" and status_filter in ("Pending", "Approved", "Rejected"):
        #print(f"DEBUG: Applying status filter: {status_filter}")
        if proj_conditions:
            proj_conditions = [*proj_conditions, Timelog.status == status_filter]
            #print(f"DEBUG: Added status filter to proj_conditions")
        else:
            # For admins with no proj_conditions, add status filter directly
            proj_conditions = [Timelog.status == status_filter]
            #print(f"DEBUG: Created new proj_conditions with status filter (admin case)")
        if user_conditions:
            user_conditions = [*user_conditions, Timelog.status == status_filter]
            #print(f"DEBUG: Added status filter to user_conditions")
    else:
        #print(f"DEBUG: Not applying status filter. status_filter={repr(status_filter)}, in_valid_values={status_filter in ('Pending', 'Approved', 'Rejected')}")
        pass
    
    # Fetch timelogs
    logs_by_project = await timelog_crud.get_many(session, *proj_conditions)
    #print(f"DEBUG: Logs by project: {len(logs_by_project)}")
    logs_by_user: List[Timelog] = []
    if user_conditions:
        logs_by_user = await timelog_crud.get_many(session, *user_conditions)
    #print(f"DEBUG: Logs by user: {len(logs_by_user)}")
    # Union results by unique timelog id
    seen = set()
    combined: List[TimelogResponse] = []
    user_id_map: Dict[int, str] = {}
    
    # Collect all unique user IDs to fetch names
    all_user_ids = set()
    for t in logs_by_project + logs_by_user:
        if t.user_id:
            all_user_ids.add(t.user_id)
    approver_ids = set(t.approver_id for t in logs_by_project + logs_by_user if getattr(t, "approver_id", None))
    
    # Fetch all user info
    user_id_map: Dict[int, Dict[str, str]] = {}
    if all_user_ids:
        user_res = await session.execute(
            select(User.id, User.username, User.first_name, User.last_name).where(User.id.in_(all_user_ids))
        )
        user_id_map = {uid: {"username": uname, "first_name": fname, "last_name": lname} for uid, uname, fname, lname in user_res.all()}
    approver_map: Dict[int, str] = {}
    if approver_ids:
        appr_res = await session.execute(
            select(User.id, User.username, User.first_name, User.last_name).where(User.id.in_(approver_ids))
        )
        for uid, uname, fname, lname in appr_res.all():
            approver_map[uid] = (f"{fname or ''} {lname or ''}".strip() or uname)
    all_timelog_ids = [t.id for t in logs_by_project + logs_by_user]
    fallback_approver_by_timelog: Dict[int, int] = {}
    if all_timelog_ids:
        latest_notifs_subq = (
            select(
                Notification.item_id.label("item_id"),
                func.max(Notification.created_at).label("latest_created_at"),
            )
            .where(
                Notification.item_type == "timelog",
                Notification.item_id.in_(all_timelog_ids),
                Notification.action.in_(["approved", "rejected"]),
            )
            .group_by(Notification.item_id)
            .subquery()
        )
        notif3_res = await session.execute(
            select(Notification.item_id, Notification.approver_id)
            .join(
                latest_notifs_subq,
                (Notification.item_id == latest_notifs_subq.c.item_id)
                & (Notification.created_at == latest_notifs_subq.c.latest_created_at),
            )
            .where(
                Notification.item_type == "timelog",
                Notification.action.in_(["approved", "rejected"]),
            )
        )
        for tlid, appr_id in notif3_res.all():
            if tlid not in fallback_approver_by_timelog:
                fallback_approver_by_timelog[tlid] = appr_id
    fallback_names: Dict[int, str] = {}
    if fallback_approver_by_timelog:
        uniq_ids2 = list(set(fallback_approver_by_timelog.values()))
        res_f = await session.execute(
            select(User.id, User.username, User.first_name, User.last_name).where(User.id.in_(uniq_ids2))
        )
        for uid, uname, fname, lname in res_f.all():
            fallback_names[uid] = (f"{fname or ''} {lname or ''}".strip() or uname)
    
    for t in logs_by_project + logs_by_user:
        if t.id in seen:
            continue
        seen.add(t.id)
        try:
            # Get the user info from the map
            user_info = user_id_map.get(t.user_id, {})
            
            # Build the response explicitly
            resp = TimelogResponse(
                id=t.id,
                user_id=t.user_id,
                username=user_info.get("username"),
                first_name=user_info.get("first_name"),
                last_name=user_info.get("last_name"),
                type=t.type,
                project_id=t.project_id,
                task_type_id=t.task_type_id,
                description=t.description,
                location=t.location,
                start_time=t.start_time,
                end_time=t.end_time,
                duration_minutes=t.duration_minutes,
                status=t.status,
                approver_id=getattr(t, "approver_id", None) or fallback_approver_by_timelog.get(t.id),
                approver_name=approver_map.get(getattr(t, "approver_id", None)) or fallback_names.get(fallback_approver_by_timelog.get(t.id, -1)),
                approved_at=getattr(t, "approved_at", None),
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            combined.append(resp)
        except Exception as e:
            import traceback
            #print(f"ERROR building timelog response {t.id}: {e}")
            #print(f"Timelog data: id={t.id}, user_id={t.user_id}, type={getattr(t, 'type', 'UNKNOWN')}, status={getattr(t, 'status', 'UNKNOWN')}, duration_minutes={getattr(t, 'duration_minutes', 'UNKNOWN')}")
            #print(f"Traceback: {traceback.format_exc()}")
            # Skip this record instead of crashing
            continue
    
    #print(f"DEBUG: Returning {len(combined)} timelogs")
    
    # Debug: Print first timelog if exists
    if combined:
        first = combined[0]
        #print(f"DEBUG: First timelog: id={first.id}, user_id={first.user_id}, type={first.type}, status={first.status}")
        #print(f"DEBUG: start_time type={type(first.start_time)}, value={first.start_time}")
        #print(f"DEBUG: end_time type={type(first.end_time)}, value={first.end_time}")
        #print(f"DEBUG: created_at type={type(first.created_at)}, value={first.created_at}")
        #print(f"DEBUG: updated_at type={type(first.updated_at)}, value={first.updated_at}")
    
    try:
        # Try to serialize the response
        from pydantic.json import pydantic_encoder
        import json
        test_json = json.dumps([c.model_dump() for c in combined], default=pydantic_encoder)
        #print(f"DEBUG: Serialization successful, length={len(test_json)}")
    except Exception as e:
        #print(f"ERROR during serialization: {e}")
        import traceback
        #print(traceback.format_exc())
    
    return combined

@router.get("/{timelog_id}", response_model=TimelogResponse)
async def get_timelog(timelog_id: int, session: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_user)):
    t = await timelog_crud.get_one(session, Timelog.id == timelog_id)
    if not t:
        raise HTTPException(status_code=404, detail="Timelog not found")
    
    # Approved tasks cannot be deleted directly. They must be Rejected first.
    if t.status == "Approved":
        raise HTTPException(status_code=403, detail="Approved timelogs cannot be deleted. Please reject it first.")

    if (user.role or "").lower() != "admin" and t.user_id != user.id:
        proj_direct_res = await session.execute(select(Project.id).where(Project.manager_id == user.id))
        proj_ids_direct = [row[0] for row in proj_direct_res.all()]
        proj_role_res = await session.execute(
            select(UserProject.project_id).where(
                UserProject.user_id == user.id,
                func.lower(UserProject.role_in_project).in_(["manager", "admin"]),
            )
        )
        proj_ids_role = [row[0] for row in proj_role_res.all()]
        managed_project_ids = {*(proj_ids_direct), *(proj_ids_role)}
        if not managed_project_ids:
            raise HTTPException(status_code=403, detail="Forbidden")
        assigned_users_res = await session.execute(
            select(UserProject.user_id).where(UserProject.project_id.in_(managed_project_ids))
        )
        managed_user_ids = {row[0] for row in assigned_users_res.all()}
        if t.type == "project":
            if t.project_id is None or t.project_id not in managed_project_ids:
                raise HTTPException(status_code=403, detail="Forbidden")
        else:
            if t.user_id not in managed_user_ids:
                raise HTTPException(status_code=403, detail="Forbidden")
    return TimelogResponse.model_validate(t, from_attributes=True)


@router.patch("/{timelog_id}", response_model=TimelogResponse)
async def update_timelog(
    timelog_id: int,
    body: UpdateTimelog,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """
    Update a timelog.
    
    Role-based access:
    - Owner: Can update all fields except status
    - Admin: Can update all fields
    - Manager/Project Manager: Can update all fields for users in their projects
    - Regular User: Can only update their own timelogs except status
    """
    t = await timelog_crud.get_one(session, Timelog.id == timelog_id)
    if not t:
        raise HTTPException(status_code=404, detail="Timelog not found")
    
    # Do not allow editing an approved timelog
    # Exception: Allow updating status to "Rejected" (to enable correction flow)
    if getattr(t, "status", None) == "Approved" and body.status != "Rejected":
        raise HTTPException(status_code=400, detail="Cannot edit an approved timelog. Please reject it first.")
    
    user_role = (user.role or "").lower()
    is_owner = t.user_id == user.id
    is_admin = user_role == "admin"
    is_status_update = "status" in body.model_dump(exclude_unset=True)
    
    # Only admins and managers/project managers can change timelog status
    if is_status_update and not is_admin:
        can_manage = await can_user_approve_timelog(user, t, session)
        
        if not can_manage:
            raise HTTPException(status_code=403, detail="You cannot approve or reject your own timelog")
    
    # Owner and admin can edit all fields
    if not is_owner and not is_admin:
        # For non-owners and non-admins, check if they're a project manager
        can_manage = await can_user_approve_timelog(user, t, session)
        
        if not can_manage:
            raise HTTPException(status_code=403, detail="Forbidden")
        
        # Project Managers have admin-like authority: can update all fields for their managed tasks
        # No restrictions
    
    # Process the update
    update_data = body.model_dump(exclude_unset=True)
    if "start_time" in update_data or "end_time" in update_data:
        new_start = "start_time" in update_data
        new_end = "end_time" in update_data
        start = update_data.get("start_time", t.start_time)
        end = update_data.get("end_time", t.end_time)
        
        def round_down(dt: datetime) -> datetime:
            minutes = (dt.minute // 15) * 15
            return dt.replace(minute=minutes, second=0, microsecond=0)
        
        def round_up(dt: datetime) -> datetime:
            minutes = ((dt.minute + 14) // 15) * 15
            if minutes == 60:
                dt = dt.replace(hour=dt.hour + 1, minute=0, second=0, microsecond=0)
            else:
                dt = dt.replace(minute=minutes, second=0, microsecond=0)
            return dt
        
        if new_start:
            start = round_down(start)
        if new_end:
            end = round_up(end)
        
        # Frontend sends aware datetimes with the browser's local timezone offset.
        # Just strip the tzinfo to store as naive local datetimes in the DB.
        body.start_time = start.replace(tzinfo=None) if start.tzinfo else start
        body.end_time = end.replace(tzinfo=None) if end.tzinfo else end
        
        gross_duration = int((end - start).total_seconds() // 60)
        # Store the actual duration
        body.duration_minutes = gross_duration
    
    t.updated_at = datetime.now().replace(microsecond=0)

    # Leave Credit Logic for Update
    new_status = update_data.get("status")
    if new_status and new_status != t.status and t.type == "leave":
        # Get task type
        tt_res = await session.execute(select(TaskType).where(TaskType.id == t.task_type_id))
        task_type = tt_res.scalars().first()
        
        if task_type:
            tt_name = task_type.name.lower()
            is_sick = "sick" in tt_name
            is_vacation = "vacation" in tt_name
            
            if is_sick or is_vacation:
                credit = await leave_credit_crud.get_by_user_id(session, t.user_id)
                if not credit:
                    credit = LeaveCredit(user_id=t.user_id)
                    session.add(credit)
                
                # Simple leave credit: 1.0 for full day, 0.5 for half day
                deduction = 0.0
                if t.duration_minutes >= 420:  # Full day or close (7+ hours)
                    deduction = 1.0
                elif t.duration_minutes >= 210:  # Half day or more (3.5+ hours)
                    deduction = 0.5
                
                # Refund if rejected
                if new_status == "Rejected":
                    if is_sick:
                        credit.sick_leave_balance += deduction
                    elif is_vacation:
                        credit.vacation_leave_balance += deduction
                    session.add(credit)
                
                # Deduct if changing from Rejected to Pending/Approved
                elif t.status == "Rejected" and new_status in ("Pending", "Approved"):
                    if is_sick:
                        credit.sick_leave_balance -= deduction
                    elif is_vacation:
                        credit.vacation_leave_balance -= deduction
                    session.add(credit)

    # If status is being updated to Approved or Rejected, set approval metadata
    if "status" in update_data and update_data["status"] in ("Approved", "Rejected"):
        t.approved_at = datetime.now().replace(microsecond=0, tzinfo=None)
        t.approver_id = user.id
        try:
            status_str = "Approved" if update_data["status"] == "Approved" else "Rejected"
            target_route = f"/tasks?status={status_str}&highlight={timelog_id}"
            notif = Notification(
                recipient_id=t.user_id,
                approver_id=user.id,
                action="approved" if update_data["status"] == "Approved" else "rejected",
                item_type="timelog",
                item_id=timelog_id,
                item_title=f"{t.type.capitalize()} Entry",
                item_description=t.description or "",
                target_route=target_route,
                is_read=0,
            )
            session.add(notif)
        except Exception:
            pass
    
    updated = await timelog_crud.update(session, t, body)
    return TimelogResponse.model_validate(updated, from_attributes=True)


@router.delete("/{timelog_id}", status_code=status.HTTP_200_OK)
async def delete_timelog(timelog_id: int, session: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_user)):
    t = await timelog_crud.get_one(session, Timelog.id == timelog_id)
    if not t:
        raise HTTPException(status_code=404, detail="Timelog not found")
    
    # Approved tasks cannot be deleted directly. They must be Rejected first.
    if t.status == "Approved":
        raise HTTPException(status_code=403, detail="Approved timelogs cannot be deleted. Please reject it first.")

    if (user.role or "").lower() != "admin" and t.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Leave Credit Refund on Delete
    if t.type == "leave" and t.status != "Rejected":
        # Get task type
        tt_res = await session.execute(select(TaskType).where(TaskType.id == t.task_type_id))
        task_type = tt_res.scalars().first()
        
        if task_type:
            tt_name = task_type.name.lower()
            is_sick = "sick" in tt_name
            is_vacation = "vacation" in tt_name
            
            if is_sick or is_vacation:
                credit = await leave_credit_crud.get_by_user_id(session, t.user_id)
                if credit:
                    # Simple leave credit: 1.0 for full day, 0.5 for half day
                    deduction = 0.0
                    if t.duration_minutes >= 420:  # Full day or close (7+ hours)
                        deduction = 1.0
                    elif t.duration_minutes >= 210:  # Half day or more (3.5+ hours)
                        deduction = 0.5
                        
                    if is_sick:
                        credit.sick_leave_balance += deduction
                    elif is_vacation:
                        credit.vacation_leave_balance += deduction
                    session.add(credit)

    await timelog_crud.delete(session, t)
    return {"message": "Timelog successfully deleted"}


@router.post("/{timelog_id}/duplicate", response_model=List[TimelogResponse])
async def duplicate_timelog(
    timelog_id: int,
    body: DuplicateTimelog,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """
    Duplicate a timelog across multiple days.
    Skips days that already have overlapping tasks.
    """
    original = await timelog_crud.get_one(session, Timelog.id == timelog_id)
    if not original:
        raise HTTPException(status_code=404, detail="Timelog not found")
    if (user.role or "").lower() != "admin" and original.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # Do not allow duplicating an approved timelog
    if getattr(original, "status", None) == "Approved":
        raise HTTPException(status_code=400, detail="Cannot duplicate an approved timelog")
    
    try:
        if isinstance(user.emp_start_date, date) and isinstance(user.emp_end_date, date):
            if body.start_date < user.emp_start_date or body.end_date > user.emp_end_date:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create timelogs within your contract period."
                )
            orig_date = original.start_time.date()
            if orig_date < user.emp_start_date or orig_date > user.emp_end_date:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create timelogs within your contract period."
                )
    except HTTPException:
        raise
    except Exception:
        pass
    
    # Call the duplicate method
    created_logs = await timelog_crud.duplicate_timelog(
        session,
        original,
        body.start_date,
        body.end_date,
        body.frequency,
    )
    
    # Leave Credit Deduction for Duplicated Logs
    if original.type == "leave":
        # Get task type
        tt_res = await session.execute(select(TaskType).where(TaskType.id == original.task_type_id))
        task_type = tt_res.scalars().first()
        
        if task_type:
            tt_name = task_type.name.lower()
            is_sick = "sick" in tt_name
            is_vacation = "vacation" in tt_name
            
            if (is_sick or is_vacation) and created_logs:
                credit = await leave_credit_crud.get_by_user_id(session, original.user_id)
                if not credit:
                    credit = LeaveCredit(user_id=original.user_id)
                    session.add(credit)
                
                total_deduction = 0.0
                for log in created_logs:
                    calc_duration = log.duration_minutes
                    
                    deduction = float(calc_duration) / 480.0
                    
                    # Snap to 0.5 or 1.0
                    if 0.45 <= deduction <= 0.55:
                        deduction = 0.5
                    elif 0.9 <= deduction <= 1.1:
                        deduction = 1.0
                        
                    total_deduction += deduction
                
                if is_sick:
                    credit.sick_leave_balance -= total_deduction
                elif is_vacation:
                    credit.vacation_leave_balance -= total_deduction
                session.add(credit)
    
    return [TimelogResponse.model_validate(log, from_attributes=True) for log in created_logs]


@router.post("/{timelog_id}/duplicate-to-dates", response_model=List[TimelogResponse])
async def duplicate_timelog_to_dates(
    timelog_id: int,
    body: DuplicateTimelogToDates,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """
    Duplicate a timelog to specific dates.
    Skips dates that already have overlapping tasks.
    """
    original = await timelog_crud.get_one(session, Timelog.id == timelog_id)
    if not original:
        raise HTTPException(status_code=404, detail="Timelog not found")
    if (user.role or "").lower() != "admin" and original.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    # Do not allow duplicating an approved timelog
    if getattr(original, "status", None) == "Approved":
        raise HTTPException(status_code=400, detail="Cannot duplicate an approved timelog")
    
    # Enforce contract date range for specific dates duplication
    try:
        if isinstance(user.emp_start_date, date) and isinstance(user.emp_end_date, date):
            for d in body.dates:
                if d < user.emp_start_date or d > user.emp_end_date:
                    raise HTTPException(
                        status_code=403,
                        detail="You can only create timelogs within your contract period."
                    )
        # Ensure original timelog date is within contract as well
        if isinstance(user.emp_start_date, date) and isinstance(user.emp_end_date, date):
            orig_date = original.start_time.date()
            if orig_date < user.emp_start_date or orig_date > user.emp_end_date:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create timelogs within your contract period."
                )
    except HTTPException:
        raise
    except Exception:
        pass

    # Call the duplicate to dates method
    created_logs = await timelog_crud.duplicate_timelog_to_dates(
        session,
        original,
        body.dates,
    )

    # Leave Credit Deduction for Duplicated Logs
    if original.type == "leave":
        # Get task type
        tt_res = await session.execute(select(TaskType).where(TaskType.id == original.task_type_id))
        task_type = tt_res.scalars().first()
        
        if task_type:
            tt_name = task_type.name.lower()
            is_sick = "sick" in tt_name
            is_vacation = "vacation" in tt_name
            
            if (is_sick or is_vacation) and created_logs:
                credit = await leave_credit_crud.get_by_user_id(session, original.user_id)
                if not credit:
                    credit = LeaveCredit(user_id=original.user_id)
                    session.add(credit)
                
                total_deduction = 0.0
                for log in created_logs:
                    calc_duration = log.duration_minutes
                    
                    deduction = float(calc_duration) / 480.0
                    
                    # Snap to 0.5 or 1.0
                    if 0.45 <= deduction <= 0.55:
                        deduction = 0.5
                    elif 0.9 <= deduction <= 1.1:
                        deduction = 1.0
                        
                    total_deduction += deduction
                
                if is_sick:
                    credit.sick_leave_balance -= total_deduction
                elif is_vacation:
                    credit.vacation_leave_balance -= total_deduction
                session.add(credit)
    
    return [TimelogResponse.model_validate(log, from_attributes=True) for log in created_logs]
