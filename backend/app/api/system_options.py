from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.database import get_async_session
from app.schemas.system_options import SystemOptionResponse, CreateSystemOption, UpdateSystemOption
from app.crud import system_options as crud_options
from app.api.dependencies import get_current_user
from app.models.users import User

router = APIRouter(
    prefix="/system-options",
    tags=["System Options"]
)

@router.get("/", response_model=List[SystemOptionResponse])
async def read_options(category: str = None, db: AsyncSession = Depends(get_async_session), current_user: User = Depends(get_current_user)):
    if category:
        return await crud_options.get_options_by_category(db, category)
    return await crud_options.get_all_options(db)

@router.post("/", response_model=SystemOptionResponse)
async def create_option(option: CreateSystemOption, db: AsyncSession = Depends(get_async_session), current_user: User = Depends(get_current_user)):
    if (current_user.role or "").lower() != 'admin':
        raise HTTPException(status_code=403, detail="Not authorized")
    return await crud_options.create_option(db, option)

@router.put("/{option_id}", response_model=SystemOptionResponse)
async def update_option(option_id: int, option: UpdateSystemOption, db: AsyncSession = Depends(get_async_session), current_user: User = Depends(get_current_user)):
    if (current_user.role or "").lower() != 'admin':
        raise HTTPException(status_code=403, detail="Not authorized")
    db_option = await crud_options.update_option(db, option_id, option)
    if not db_option:
        raise HTTPException(status_code=404, detail="Option not found")
    return db_option

@router.delete("/{option_id}")
async def delete_option(option_id: int, db: AsyncSession = Depends(get_async_session), current_user: User = Depends(get_current_user)):
    if (current_user.role or "").lower() != 'admin':
        raise HTTPException(status_code=403, detail="Not authorized")
    await crud_options.delete_option(db, option_id)
    return {"message": "Option deleted"}
