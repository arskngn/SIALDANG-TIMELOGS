from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_async_session
from app.api.dependencies import get_current_admin, get_current_user
from app.models.roles import Role


router = APIRouter(
    prefix="/role",
    tags=["Roles"],
    responses={404: {"description": "Role not found"}},
)


@router.get("/", response_model=List[str])
async def list_roles(session: AsyncSession = Depends(get_async_session), admin=Depends(get_current_admin)):
    result = await session.execute(select(Role.role_name))
    names = [row[0] for row in result.all()]
    return sorted(names)


@router.get("/all", response_model=List[str])
async def list_roles_public(session: AsyncSession = Depends(get_async_session), user=Depends(get_current_user)):
    result = await session.execute(select(Role.role_name))
    names = [row[0] for row in result.all()]
    return sorted(names)

