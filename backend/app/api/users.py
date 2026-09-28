
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.users import CreateUser, UserResponse, UpdateUser, ProjectsAssignRequest, ProjectAssignment
from app.models.users import User
from app.database import get_async_session
from app.crud.users import user_crud
from typing import List, Dict
from sqlalchemy import select, delete, func, update
from app.models.roles import Role
from app.models.user_projects import UserProject
from app.models.projects import Project
from app.models.timelogs import Timelog
from app.models.leave_credits import LeaveCredit
from app.models.user_201_files import User201File
from app.schemas.projects import ProjectResponse
from app.api.dependencies import get_current_user, get_current_admin, get_current_manager
from app.security import get_password_hash, USER_SENSITIVE_FIELDS, decrypt_value
from app.utils.user_utils import get_user_status, is_user_account_active
from datetime import datetime, timezone, date
from typing import Any, Dict as TypingDict


def _decrypt_sensitive_fields(user_orm: User) -> TypingDict[str, Any]:
    updates: TypingDict[str, Any] = {}
    for field in USER_SENSITIVE_FIELDS:
        if hasattr(user_orm, field):
            value = getattr(user_orm, field)
            if value is not None:
                try:
                    decrypted = decrypt_value(value)
                    updates[field] = decrypted
                except Exception:
                    updates[field] = value
    return updates


def _add_status_to_response(user_orm: User) -> dict:
    resp = UserResponse.model_validate(user_orm, from_attributes=True)
    updates: TypingDict[str, Any] = {}
    updates.update(_decrypt_sensitive_fields(user_orm))
    status_value = get_user_status(user_orm.emp_start_date, user_orm.emp_end_date)
    updates["status"] = status_value
    return resp.model_copy(update=updates).model_dump()


def _user_to_response(user_orm: User) -> UserResponse:
    resp = UserResponse.model_validate(user_orm, from_attributes=True)
    updates: TypingDict[str, Any] = {}
    updates.update(_decrypt_sensitive_fields(user_orm))
    status_value = get_user_status(user_orm.emp_start_date, user_orm.emp_end_date)
    updates["status"] = status_value
    return resp.model_copy(update=updates)

router = APIRouter(
    prefix="/user", # Fixed: Changed from /users to /user to match frontend
    tags=["Users"],
    responses={404: {"description": "User not found"}}
)


@router.get("/", response_model=List[UserResponse], summary="List Users")
async def list_users(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """
    Retrieve users from the database.

    Access rules:
    - Admin: Can see all users
    - Manager: Can see users in projects they manage
    - User: Can only see themselves
    """
    try:
        user_role = (user.role or "").lower()

        if user_role == "admin" or user_role == "manager":
            # Admin can see all users
            user_orm_list = await user_crud.get_many(session)
        
        # elif user_role == "manager":
        #     # Get projects managed by this manager
        #     project_res = await session.execute(
        #         select(Project.id).where(
        #             Project.manager_id == user.id
        #         )
        #     )

        #     project_ids = [row[0] for row in project_res.all()]

        #     if project_ids:
        #         # Get users assigned to those projects
        #         user_project_res = await session.execute(
        #             select(UserProject.user_id).where(
        #                 UserProject.project_id.in_(project_ids)
        #             )
        #         )

        #         user_ids = {row[0] for row in user_project_res.all()}

        #         # Include the manager themselves
        #         user_ids.add(user.id)

        #         user_orm_list = await user_crud.get_many(
        #             session,
        #             User.id.in_(user_ids)
        #         )
            
        #     else:
        #         # Manager has no projects
        #         user_orm_list = [user]
            
        else:
            # Regular user can only see themselves
            user_orm_list = [user]

        return [
            _user_to_response(user_orm)
            for user_orm in user_orm_list
        ]

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving users: {str(e)}"
        )

@router.get(
    "/my-managed",
    response_model=List[UserResponse],
    summary="List Users in My Managed Projects"
)
async def list_my_managed_users(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_manager),
):
    """
    Retrieve users managed by the current user.

    Access rules:
    - Admin: Can see all users
    - Manager: Can see users assigned to projects they manage
    - Regular user: Not allowed
    """
    try:
        user_role = (user.role or "").lower()

        # Admin can see all users
        if user_role == "admin":
            user_orm_list = await user_crud.get_many(session)

        # Manager can see users in projects they manage
        elif user_role == "manager":
            # Get projects managed by this manager
            project_res = await session.execute(
                select(Project.id).where(
                    Project.manager_id == user.id
                )
            )

            project_ids = [row[0] for row in project_res.all()]

            if not project_ids:
                return []

            # Get users assigned to those projects
            user_project_res = await session.execute(
                select(UserProject.user_id).where(
                    UserProject.project_id.in_(project_ids)
                )
            )

            user_ids = {row[0] for row in user_project_res.all()}

            # Include the manager themselves
            user_ids.add(user.id)

            user_orm_list = await user_crud.get_many(
                session,
                User.id.in_(user_ids)
            )

        else:
            # Regular users cannot access this endpoint
            raise HTTPException(
                status_code=403,
                detail="Only admins and managers can access this endpoint"
            )

        return [
            _user_to_response(user_orm)
            for user_orm in user_orm_list
        ]

    except HTTPException:
        raise

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving managed users: {str(e)}"
        )


@router.post("/", response_model=UserResponse, summary="Create User")
async def create_user(user: CreateUser, session: AsyncSession = Depends(get_async_session), current_user: User = Depends(get_current_admin)):

    # Prevent duplicate username
    exists = await user_crud.get_one(session, User.username == user.username)
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    # Prevent duplicate email if provided
    if getattr(user, "email", None):
        exists_email = await user_crud.get_one(session, User.email == user.email)
        if exists_email:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    # Convert branch_id=0 to None (invalid foreign key reference)
    if hasattr(user, "branch_id") and user.branch_id == 0:
        user.branch_id = None
    # Hash password and set timestamps server-side
    user.password = get_password_hash(user.password)
    now_utc = datetime.now(timezone.utc)
    user.date_created = now_utc.replace(tzinfo=None)
    user.date_updated = now_utc.replace(tzinfo=None)

    # Map role -> role_id using case-insensitive match against roles table
    if getattr(user, "role", None):
        role_value = (user.role or "").strip().lower()
        res = await session.execute(select(Role).where(func.lower(Role.role_name) == role_value))
        matched = res.scalars().first()
        if matched:
            user.role_id = matched.id  # type: ignore[attr-defined]

    user_orm: User = await user_crud.create(session, user)
    return _user_to_response(user_orm)

@router.get("/me", response_model=UserResponse, summary="Get Current User")
async def get_me(session: AsyncSession = Depends(get_async_session), current_user: User = Depends(get_current_user)):
    return _user_to_response(current_user)

@router.get("/{user_id}", response_model=UserResponse, summary="Get User")
async def get_user(user_id: int, session: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_admin)):
    """
    Retrieve a specific user by ID.
    
    Parameters:
    - user_id: Unique identifier of the user
    
    Returns the user details if found, or 404 if not found.
    """
    user_orm = await user_crud.get_one(session, User.id == user_id)
    if not user_orm:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_response(user_orm)

@router.patch("/me", response_model=UserResponse, summary="Update current user")
async def update_me(
    user_update: UpdateUser,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """
    Allow the current authenticated user to update their own profile.

    Access rules:
    - Admin: Can update all fields
    - Manager/User: Cannot update restricted fields
    """

    user_role = (current_user.role or "").lower()

    # Restricted fields apply only to non-admin users
    if user_role != "admin":
        forbidden_fields = [
            "role",
            "phone_number",
            "civil_status",
            "birthdate",
            "permanent_address_line",
            "permanent_address_psgc",
            "first_name",
            "last_name",
            "salutation",
            "username",
            "role_id",
            "branch_id",
            "email",
            "department",
            "job_level",
            "emp_start_date",
            "emp_end_date",
            "blocked"
        ]

        for field in forbidden_fields:
            if getattr(user_update, field, None) is not None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not allowed to change {field}"
                )

    # Hash password if provided
    if getattr(user_update, "password", None):
        user_update.password = get_password_hash(
            user_update.password
        )  # type: ignore[attr-defined]

    # Update timestamp
    now_utc = datetime.now(timezone.utc)
    user_update.date_updated = now_utc.replace(tzinfo=None)

    # Check email uniqueness
    if getattr(user_update, "email", None):
        exists_email = await user_crud.get_one(
            session,
            User.email == user_update.email
        )

        if exists_email and exists_email.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use"
            )

    # Check username uniqueness
    if getattr(user_update, "username", None):
        exists_username = await user_crud.get_one(
            session,
            User.username == user_update.username
        )

        if exists_username and exists_username.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already in use"
            )

    updated = await user_crud.update(
        session,
        current_user,
        user_update
    )

    return _user_to_response(updated)

@router.patch("/{user_id}", response_model=UserResponse, summary="Update User")
async def update_user(user_id: int, user_update: UpdateUser, session: AsyncSession = Depends(get_async_session), current_user: User = Depends(get_current_admin)):
    """
    Update a specific user's details.
    
    Parameters:
    - user_id: Unique identifier of the user
    - user_update: User fields to update (all fields optional)
    
    Returns the updated user details.
    """
    user_orm = await user_crud.get_one(session, User.id == user_id)
    if not user_orm:
        raise HTTPException(status_code=404, detail="User not found")
    # If password is being updated, hash it
    if getattr(user_update, "password", None):
        user_update.password = get_password_hash(user_update.password)  # type: ignore[attr-defined]

    # Convert branch_id=0 to None (invalid foreign key reference) — admins only
    if (current_user.role or "").lower() == "admin" and hasattr(user_update, "branch_id") and user_update.branch_id == 0:
        user_update.branch_id = None

    # Set server-side timestamp for update
    now_utc = datetime.now(timezone.utc)
    user_update.date_updated = now_utc.replace(tzinfo=None)
    # Check uniqueness for email when updating
    if getattr(user_update, "email", None):
        exists_email = await user_crud.get_one(session, User.email == user_update.email)
        if exists_email and exists_email.id != user_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    # Allow only admins to change blocked flag
    if (current_user.role or "").lower() != "admin" and getattr(user_update, "blocked", None) is not None:
        user_update.blocked = None

    # Map role -> role_id when role string is being updated — admins only
    if (current_user.role or "").lower() == "admin" and getattr(user_update, "role", None):
        role_value = (user_update.role or "").strip().lower()
        res = await session.execute(select(Role).where(func.lower(Role.role_name) == role_value))
        matched = res.scalars().first()
        if matched:
            user_update.role_id = matched.id  # type: ignore[attr-defined]

    user_orm = await user_crud.update(session, user_orm, user_update)
    return _user_to_response(user_orm)

@router.post("/{user_id}/reactivate", response_model=UserResponse, summary="Reactivate User with New Contract")
async def reactivate_user(
    user_id: int,
    emp_start_date: date,
    emp_end_date: date,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_admin)
):
    """
    Reactivate an inactive user by updating their contract dates.
    
    Parameters:
    - user_id: ID of the user to reactivate
    - emp_start_date: New employment start date
    - emp_end_date: New employment end date
    
    Returns the updated user with new status.
    """
    # Validate dates
    if emp_start_date >= emp_end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="emp_start_date must be before emp_end_date")
    
    # Get user
    user_orm = await user_crud.get_one(session, User.id == user_id)
    if not user_orm:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update contract dates
    user_orm.emp_start_date = emp_start_date
    user_orm.emp_end_date = emp_end_date
    user_orm.date_updated = datetime.now(timezone.utc).replace(tzinfo=None)
    
    # Persist changes
    session.add(user_orm)
    await session.commit()
    await session.refresh(user_orm)
    
    # Return response with status
    return _user_to_response(user_orm)

@router.delete("/{user_id}", status_code=status.HTTP_200_OK, summary="Delete User")
async def delete_user(user_id: int, session: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_admin)):
    """
    Remove a user from the system.
    
    Parameters:
    - user_id: Unique identifier of the user to delete
    
    Returns a success message if the user was deleted.
    """
    if user_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account while logged in")
    user_orm = await user_crud.get_one(session, User.id == user_id)
    if not user_orm:
        raise HTTPException(status_code=404, detail="User not found")
    # Clean up dependent records to avoid FK constraint violations
    # Remove project assignments
    await session.execute(delete(UserProject).where(UserProject.user_id == user_id))
    # Null out manager assignments on projects managed by this user
    await session.execute(update(Project).where(Project.manager_id == user_id).values(manager_id=None, manager_role_id=None))
    # Null out approver on timelogs approved by this user
    await session.execute(update(Timelog).where(Timelog.approver_id == user_id).values(approver_id=None, approved_at=None))
    # Delete timelogs created by this user
    await session.execute(delete(Timelog).where(Timelog.user_id == user_id))
    # Delete 201 files owned by this user
    await session.execute(delete(User201File).where(User201File.user_id == user_id))
    # Delete leave credits record for this user
    await session.execute(delete(LeaveCredit).where(LeaveCredit.user_id == user_id))
    await session.commit()
    await user_crud.delete(session, user_orm)
    return {"message": "User successfully deleted"}


@router.post("/role-id/backfill", summary="Backfill role_id for existing users")
async def backfill_role_ids(session: AsyncSession = Depends(get_async_session), admin: User = Depends(get_current_admin)):
    """Set users.role_id based on users.role for records where role_id is NULL."""
    result = await session.execute(select(User).where(User.role_id.is_(None)))
    users = result.scalars().all()
    updated = 0
    for u in users:
        role_value = (u.role or "").strip().lower()
        if not role_value:
            continue
        r_res = await session.execute(select(Role).where(func.lower(Role.role_name) == role_value))
        r = r_res.scalars().first()
        if r:
            u.role_id = r.id
            session.add(u)
            updated += 1
    if updated:
        await session.commit()
    return {"updated": updated}



@router.patch("/{user_id}/projects", response_model=List[ProjectResponse], summary="Assign projects to user")
async def assign_projects(
    user_id: int,
    payload: ProjectsAssignRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    user_orm = await user_crud.get_one(session, User.id == user_id)
    if not user_orm:
        raise HTTPException(status_code=404, detail="User not found")

    # Normalize payload to assignments list
    assignments = []
    if payload.assignments:
        assignments = payload.assignments
    elif payload.project_ids:
        assignments = [ProjectAssignment(project_id=pid) for pid in payload.project_ids]

    if assignments:
        p_ids = [a.project_id for a in assignments]
        result = await session.execute(select(Project.id).where(Project.id.in_(p_ids)))
        existing_ids = set(result.scalars().all())
        requested_ids = set(p_ids)
        missing = requested_ids - existing_ids
        if missing:
            raise HTTPException(status_code=404, detail=f"Projects not found: {sorted(missing)}")

    await session.execute(delete(UserProject).where(UserProject.user_id == user_id))
    
    for item in assignments:
        role_id_val = item.role_id
        role_name_val = user_orm.role # Default to user's global role name
        
        # If role_id provided, fetch name
        if role_id_val:
             r_res = await session.get(Role, role_id_val)
             if r_res:
                 role_name_val = r_res.role_name
        
        # If no role_id provided, try to resolve from global role
        elif role_name_val:
            res = await session.execute(select(Role).where(func.lower(Role.role_name) == func.lower(role_name_val)))
            role = res.scalars().first()
            if role:
                role_id_val = role.id
                role_name_val = role.role_name # Use canonical name
        
        # When assigning a user to a project, always mark them as "project_manager"
        # so they have authority to manage timelogs for that project
        project_role = "project_manager"
                
        session.add(
            UserProject(
                user_id=user_id,
                project_id=item.project_id,
                role_in_project=project_role,
                role_id=role_id_val,
            )
        )
    await session.commit()

    result = await session.execute(
        select(Project).join(UserProject, UserProject.project_id == Project.id).where(UserProject.user_id == user_id)
    )
    projects = result.scalars().all()
    return [ProjectResponse.model_validate(p, from_attributes=True) for p in projects]

@router.get("/me/projects", response_model=List[ProjectResponse], summary="List projects for current user")
async def get_my_projects(session: AsyncSession = Depends(get_async_session), current_user: User = Depends(get_current_user)):
    manager_result = await session.execute(select(Project).where(Project.manager_id == current_user.id))
    manager_projects = manager_result.scalars().all()
    assigned_result = await session.execute(
        select(Project).join(UserProject, UserProject.project_id == Project.id).where(UserProject.user_id == current_user.id)
    )
    assigned_projects = assigned_result.scalars().all()
    unique = {}
    for p in manager_projects + assigned_projects:
        unique[p.id] = p
    projects = list(unique.values())
    ids = {p.manager_id for p in projects if p.manager_id is not None}
    name_map: Dict[int, str] = {}
    if ids:
        res = await session.execute(select(User.id, User.username, User.first_name, User.last_name).where(User.id.in_(ids)))
        for uid, uname, fname, lname in res.all():
            full = f"{(fname or '').strip()} {(lname or '').strip()}".strip()
            name_map[uid] = full or uname
    return [ProjectResponse.model_validate(p, from_attributes=True).model_copy(update={"manager_username": name_map.get(p.manager_id)}) for p in projects]

@router.get("/{user_id}/projects", response_model=List[ProjectResponse], summary="List projects assigned to user")
async def get_user_projects(user_id: int, session: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_admin)):
    manager_result = await session.execute(select(Project).where(Project.manager_id == user_id))
    manager_projects = manager_result.scalars().all()
    assigned_result = await session.execute(
        select(Project).join(UserProject, UserProject.project_id == Project.id).where(UserProject.user_id == user_id)
    )
    assigned_projects = assigned_result.scalars().all()
    unique = {}
    for p in manager_projects + assigned_projects:
        unique[p.id] = p
    projects = list(unique.values())
    ids = {p.manager_id for p in projects if p.manager_id is not None}
    name_map: Dict[int, str] = {}
    if ids:
        res = await session.execute(select(User.id, User.username, User.first_name, User.last_name).where(User.id.in_(ids)))
        for uid, uname, fname, lname in res.all():
            full = f"{(fname or '').strip()} {(lname or '').strip()}".strip()
            name_map[uid] = full or uname
    return [ProjectResponse.model_validate(p, from_attributes=True).model_copy(update={"manager_username": name_map.get(p.manager_id)}) for p in projects]

