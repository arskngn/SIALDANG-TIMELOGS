from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_async_session
from app.api.dependencies import get_current_admin, get_current_user
from app.models.branches import Branch
from app.models.users import User
from app.models.projects import Project
from sqlalchemy import update
from app.schemas.branches import CreateBranch, UpdateBranch, BranchResponse
from app.crud.branches import branch_crud

router = APIRouter(
    prefix="/branch",
    tags=["Branches"],
    responses={404: {"description": "Branch not found"}},
)

@router.get("/", response_model=List[BranchResponse])
async def list_branches(session: AsyncSession = Depends(get_async_session), user: Branch = Depends(get_current_admin)):
    branches = await branch_crud.get_many(session)
    return [BranchResponse.model_validate(b, from_attributes=True) for b in branches]

@router.get("/all", response_model=List[BranchResponse])
async def list_branches_public(session: AsyncSession = Depends(get_async_session), user: Branch = Depends(get_current_user)):
    branches = await branch_crud.get_many(session)
    return [BranchResponse.model_validate(b, from_attributes=True) for b in branches]

@router.post("/", response_model=BranchResponse)
async def create_branch(branch: CreateBranch, session: AsyncSession = Depends(get_async_session), user: Branch = Depends(get_current_admin)):
    created = await branch_crud.create(session, branch)
    return BranchResponse.model_validate(created, from_attributes=True)

@router.get("/{branch_id}", response_model=BranchResponse)
async def get_branch(branch_id: int, session: AsyncSession = Depends(get_async_session), user: Branch = Depends(get_current_admin)):
    branch = await branch_crud.get_one(session, Branch.id == branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    return BranchResponse.model_validate(branch, from_attributes=True)

@router.patch("/{branch_id}", response_model=BranchResponse)
async def update_branch(branch_id: int, branch_update: UpdateBranch, session: AsyncSession = Depends(get_async_session), user: Branch = Depends(get_current_admin)):
    branch = await branch_crud.get_one(session, Branch.id == branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    updated = await branch_crud.update(session, branch, branch_update)
    return BranchResponse.model_validate(updated, from_attributes=True)

@router.delete("/{branch_id}", status_code=status.HTTP_200_OK)
async def delete_branch(branch_id: int, session: AsyncSession = Depends(get_async_session), user: Branch = Depends(get_current_admin)):
    branch = await branch_crud.get_one(session, Branch.id == branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    # Null out references from users and projects to allow deletion
    await session.execute(update(User).where(User.branch_id == branch_id).values(branch_id=None))
    await session.execute(update(Project).where(Project.branch_id == branch_id).values(branch_id=None))
    await session.commit()
    await branch_crud.delete(session, branch)
    return {"message": "Branch successfully deleted"}
