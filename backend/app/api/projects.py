from typing import List, Dict, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_async_session
from app.api.dependencies import get_current_admin, get_current_user, get_current_manager
from app.models.projects import Project
from app.models.users import User
from app.crud.users import user_crud
from app.schemas.projects import CreateProject, UpdateProject, ProjectResponse,CreateProjectResource,UpdateProjectResource,FTE, UpdateProjectResourceInDB
from app.models.roles import Role
from sqlalchemy import select, delete, update
from sqlalchemy import func
from app.crud.projects import project_crud
from app.crud.user_projects import user_project_crud
from app.models.user_projects import UserProject
from app.models.timelogs import Timelog

def calculate_project_status(start_date: Optional[date], end_date: Optional[date]) -> str:
    today = date.today()
    if start_date and start_date > today:
        return "Pending"
    if end_date and end_date < today:
        return "Completed"
    if start_date and start_date <= today:
        return "Ongoing"
    return "Pending"

router = APIRouter(
    prefix="/project",
    tags=["Projects"],
    responses={404: {"description": "Project not found"}},
)

@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    session: AsyncSession = Depends(get_async_session),
    current: User = Depends(get_current_user),
):
    """
    List all projects accessible to the current user.
    
    Access rules:
    - Admin: See all projects
    - Manager: See all projects (can manage any project)
    - Project Manager assignment: See projects assigned to them
    - User: See only projects they are assigned to
    """
    role = (current.role or "").lower()
    #print(f"DEBUG list_projects: user_id={current.id}, role={role}, customer_id={customer_id}")
    
    if role =='admin':
        # Admin and managers can see all projects
        filters = []
        if customer_id:
            filters.append(Project.customer_id == customer_id)
        
        projects = await project_crud.get_many(session, *filters)
        #print(f"DEBUG list_projects: admin/manager, found {len(projects)} projects")
    else:
        # All other users see only their assigned projects
        query = select(Project).join(UserProject, UserProject.project_id == Project.id).where(
                UserProject.user_id == current.id,
            )
        if customer_id:
            query = query.where(Project.customer_id == customer_id)
            
        assigned_res = await session.execute(query)
        projects = assigned_res.scalars().all()
        #print(f"DEBUG list_projects: regular user, found {len(projects)} projects")
    
    # Update project status based on date
    today = date.today()
    updated_any = False
    for p in projects:
        new_status = None
        # Logic:
        # - Future start date -> Pending
        # - Past end date -> Completed
        # - Current date between start and end (or no end) -> Ongoing
        
        if p.start_date and p.start_date > today:
            new_status = "Pending"
        elif p.end_date and p.end_date < today:
            new_status = "Completed"
        elif p.start_date and p.start_date <= today:
            new_status = "Ongoing"
            
        if new_status and p.status != new_status:
            p.status = new_status
            updated_any = True
            
    if updated_any:
        await session.commit()
    
    # Get manager display names
    ids = {p.manager_id for p in projects if p.manager_id is not None}
    name_map: Dict[int, str] = {}
    if ids:
        res = await session.execute(select(User.id, User.username, User.first_name, User.last_name).where(User.id.in_(ids)))
        for uid, uname, fname, lname in res.all():
            full = f"{(fname or '').strip()} {(lname or '').strip()}".strip()
            name_map[uid] = full or uname
    
    return [ProjectResponse.model_validate(p, from_attributes=True).model_copy(
        update={"manager_username": name_map.get(p.manager_id)}
    ) for p in projects]

@router.post("/", response_model=ProjectResponse)
async def create_project(
    project: CreateProject,
    session: AsyncSession = Depends(get_async_session),
    current: User = Depends(get_current_user),
):
    """
    Create a new project.
    
    Role-based access:
    - Admin: Can create projects and assign any manager
    - Manager: Can create projects and assign themselves or other managers as project lead
    - User with project assignment: Cannot create projects
    
    Project managers can be:
    - Set as the project's manager_id (primary manager)
    - Assigned through user_projects with role 'Project Manager' (additional project managers)
    """
    # Only admin and manager roles can create projects
    user_role = (current.role or "").lower()
    if user_role not in ("admin", "manager"):
        raise HTTPException(
            status_code=403,
            detail="Only admins and managers can create projects"
        )
    
    # If manager_id is not provided, set it to the current user
    if project.manager_id is None:
        project.manager_id = current.id
    
    if project.manager_id is not None:
        manager = await user_crud.get_one(session, User.id == project.manager_id, User.role.in_(['manager','admin']))
        if manager is None:
            raise HTTPException(status_code=404, detail="Manager user not found")
        if project.manager_role_id is None:
            res = await session.execute(select(Role).where(Role.role_name == manager.role))
            role = res.scalars().first()
            if role:
                project.manager_role_id = role.id
    
    created = await project_crud.create(session, project)
    
    # Add the manager to user_projects with "Project Manager" role
    if created.manager_id is not None:
        user_project = UserProject(
            user_id=created.manager_id,
            project_id=created.id,
            role_in_project="project_manager",
            fte=FTE.FULL_TIME.value
            )
        session.add(user_project)
        await session.commit()
    
    name = None
    if created.manager_id is not None:
        res = await session.execute(select(User.username, User.first_name, User.last_name).where(User.id == created.manager_id))
        row = res.first()
        if row:
            uname, fname, lname = row
            full = f"{(fname or '').strip()} {(lname or '').strip()}".strip()
            name = full or uname
    return ProjectResponse.model_validate(created, from_attributes=True).model_copy(update={"manager_username": name})

# Place static route before dynamic `/{project_id}` to avoid 422 on '/my-managed'
@router.get("/my-managed", response_model=List[ProjectResponse])
async def list_my_managed_projects(session: AsyncSession = Depends(get_async_session), current=Depends(get_current_user)):
    """
    Get projects where current user is assigned as project manager.
    
    Only users with project manager assignment will see projects here.
    Managers without project assignment won't see any projects.
    Admin can see all projects.
    """
    role = (current.role or "").lower()
    
    # Get all projects if admin, otherwise get projects where user is assigned as project manager
    if role == "admin":
        assigned_res = await session.execute(
            select(Project)
        )
    else:
        assigned_res = await session.execute(
            select(Project).join(UserProject, UserProject.project_id == Project.id).where(
                UserProject.user_id == current.id,
                func.lower(UserProject.role_in_project) == "project_manager",
            )
        )
    projects = assigned_res.scalars().all()
    
    ids = {p.manager_id for p in projects if p.manager_id is not None}
    name_map: Dict[int, str] = {}
    if ids:
        res = await session.execute(select(User.id, User.username, User.first_name, User.last_name).where(User.id.in_(ids)))
        for uid, uname, fname, lname in res.all():
            full = f"{(fname or '').strip()} {(lname or '').strip()}".strip()
            name_map[uid] = full or uname
    return [ProjectResponse.model_validate(p, from_attributes=True).model_copy(update={"manager_username": name_map.get(p.manager_id)}) for p in projects]

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    session: AsyncSession = Depends(get_async_session),
    current: User = Depends(get_current_user),
):
    """
    Get a specific project.
    
    Access rules:
    - Admin: Can view any project
    - Manager/Project Manager: Can view projects they manage or are assigned to
    - User: Can view projects they are assigned to
    """
    project = await project_crud.get_one(session, Project.id == project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    role = (current.role or "").lower()
    
    # Admin can see everything
    if role == "admin":
        pass  # Allow access
    else:
        # Check if user is the direct manager
        is_direct_manager = project.manager_id == current.id
        
        # Check if user is assigned to this project
        assigned_res = await session.execute(
            select(UserProject).where(
                UserProject.project_id == project_id,
                UserProject.user_id == current.id,
            )
        )
        is_assigned = assigned_res.scalars().first() is not None
        
        if not (is_direct_manager or is_assigned):
            raise HTTPException(status_code=403, detail="Forbidden")
    
    name = None
    if project.manager_id is not None:
        res = await session.execute(select(User.username, User.first_name, User.last_name).where(User.id == project.manager_id))
        row = res.first()
        if row:
            uname, fname, lname = row
            full = f"{(fname or '').strip()} {(lname or '').strip()}".strip()
            name = full or uname
    
    return ProjectResponse.model_validate(project, from_attributes=True).model_copy(
        update={"manager_username": name}
    )

@router.get("/{project_id}/users", response_model=List[Dict])
async def get_project_users(project_id: int, session: AsyncSession = Depends(get_async_session), current: User = Depends(get_current_user)):
    # Verify project exists
    project = await project_crud.get_one(session, Project.id == project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Fetch all users assigned to this project
    res = await session.execute(
        select(User.id, User.username, User.first_name, User.last_name, User.email, UserProject.role_in_project, UserProject.fte).join(
            UserProject, UserProject.user_id == User.id
        ).where(UserProject.project_id == project_id)
    )
    users = []
    for uid, username, fname, lname, email, role, fte in res.all():
        full = f"{(fname or '').strip()} {(lname or '').strip()}".strip()
        users.append({
            "id": uid, 
            "username": username, 
            "full_name": full or username,
            "email": email,
            "role_in_project": role,
            "fte": fte
        })
    return users

@router.post("/resources", summary="Add User to Project")
async def add_project_resource(
    payload:CreateProjectResource,
    session: AsyncSession = Depends(get_async_session),
    current: User = Depends(get_current_manager)
):
    project = await project_crud.get_one(session, Project.id == payload.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    role = (current.role or "").lower()
    if role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Forbidden")
    else:
        if role == 'manager' and project.manager_id != current.id:
            raise HTTPException(status_code=403, detail="Forbidden")
        
    # Check if user exists
    user = await user_crud.get_one(session, User.id == payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Check if already assigned
    existing = await session.execute(
        select(UserProject).where(
            UserProject.project_id == payload.project_id,
            UserProject.user_id == payload.user_id
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="User already assigned to this project")
        
    new_assignment = UserProject(
        user_id=payload.user_id,
        project_id=payload.project_id,
        role_in_project=payload.role_in_project,
        fte=payload.fte.value
    )
    session.add(new_assignment)
    await session.commit()
    await session.refresh(new_assignment)
    return {"message": "User added to project successfully"}

@router.patch("/{project_id}/resources/{user_id}", summary="Update Project Resource")
async def update_project_resource(
    project_id: int,
    user_id: int,
    payload: UpdateProjectResource,
    session: AsyncSession = Depends(get_async_session),
    current: User = Depends(get_current_manager)
):
    # Check if project exists
    project = await project_crud.get_one(
        session,
        Project.id == project_id
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check manager/admin permission
    role = (current.role or "").lower()

    if role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Forbidden")

    if role == "manager" and project.manager_id != current.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Find existing project resource
    existing = await session.execute(
        select(UserProject).where(
            UserProject.project_id == project_id,
            UserProject.user_id == user_id
        )
    )
    resource = existing.scalars().first()

    if not resource:
        raise HTTPException(
            status_code=404,
            detail="User is not assigned to this project"
        )

    # Transform API payload into DB-safe payload
    db_payload = UpdateProjectResourceInDB(
        **payload.model_dump(exclude_unset=True)
    )

    await user_project_crud.update(
        session,
        resource,
        db_payload
    )

    return {"message": "Project resource updated successfully"}

@router.delete("/{project_id}/resources/{user_id}", summary="Remove User from Project")
async def remove_project_resource(
    project_id: int,
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
    current: User = Depends(get_current_manager)
):
    
    project = await project_crud.get_one(session, Project.id == project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    role = (current.role or "").lower()
    if role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Forbidden")
    else:
        if role == 'manager' and project.manager_id != current.id:
            raise HTTPException(status_code=403, detail="Forbidden")
                
    assignment = await session.execute(
        select(UserProject).where(
            UserProject.project_id == project_id,
            UserProject.user_id == user_id
        )
    )
    db_obj = assignment.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="User not assigned to this project")
        
    await session.delete(db_obj)
    await session.commit()
    return {"message": "User removed from project successfully"}

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: int, project_update: UpdateProject, session: AsyncSession = Depends(get_async_session), current: User = Depends(get_current_manager)):
  
    project = await project_crud.get_one(session, Project.id == project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    role = (current.role or "").lower()
    if role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Forbidden")
    else:
        if role == 'manager' and project.manager_id != current.id:
            raise HTTPException(status_code=403, detail="Forbidden")
        
    if getattr(project_update, "manager_id", None) is not None:
        manager = await user_crud.get_one(session, User.id == project_update.manager_id, User.role.in_(['admin','manager']) )
        if manager is None:
            raise HTTPException(status_code=404, detail="Manager user not found")
        if getattr(project_update, "manager_role_id", None) is None:
            res = await session.execute(select(Role).where(Role.role_name == manager.role))
            role = res.scalars().first()
            if role:
                project_update.manager_role_id = role.id
        
        # Add the manager to user_projects with "project_manager" role
        manager_id = project_update.manager_id
        
        # Remove any existing project_manager assignments for this project
        # to ensure only the new manager has project_manager authority
        await session.execute(
            delete(UserProject).where(
                UserProject.project_id == project_id,
                func.lower(UserProject.role_in_project) == "project_manager"
            )
        )
        
        # Add the new manager to user_projects
        user_project = UserProject(
            user_id=manager_id,
            project_id=project_id,
            role_in_project="project_manager",
            fte=FTE.FULL_TIME.value
        )
        session.add(user_project)
    
    # Update status based on new or existing dates
    new_start = project_update.start_date if project_update.start_date is not None else project.start_date
    new_end = project_update.end_date if project_update.end_date is not None else project.end_date
    project_update.status = calculate_project_status(new_start, new_end)

    updated = await project_crud.update(session, project, project_update)
    await session.commit()
    name = None
    if updated.manager_id is not None:
        res = await session.execute(select(User.username, User.first_name, User.last_name).where(User.id == updated.manager_id))
        row = res.first()
        if row:
            uname, fname, lname = row
            full = f"{(fname or '').strip()} {(lname or '').strip()}".strip()
            name = full or uname
    return ProjectResponse.model_validate(updated, from_attributes=True).model_copy(update={"manager_username": name})

@router.delete("/{project_id}", status_code=status.HTTP_200_OK)
async def delete_project(project_id: int, session: AsyncSession = Depends(get_async_session), current: User = Depends(get_current_manager)):
    
    project = await project_crud.get_one(session, Project.id == project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    role = (current.role or "").lower()
    if role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Forbidden")
    else:
        if role == 'manager' and project.manager_id != current.id:
            raise HTTPException(status_code=403, detail="Forbidden")
    result = await session.execute(select(Timelog).where(Timelog.project_id == project_id))
    if result.scalars().first():
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete project with associated timelogs. Please delete the timelogss first."
        )
    #print(f"DEBUG delete_project: user_id={current.id}, role={current.role}, role_lower={role}")
    
    # Remove user-project assignments and null out timelog project references
    await session.execute(delete(UserProject).where(UserProject.project_id == project_id))
    await session.execute(update(Timelog).where(Timelog.project_id == project_id).values(project_id=None))
    await session.commit()
    await project_crud.delete(session, project)
    return {"message": "Project successfully deleted"}
