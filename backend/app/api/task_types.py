from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_async_session
from app.api.dependencies import get_current_admin, get_current_user
from app.models.task_types import TaskType
from app.schemas.task_types import CreateTaskType, UpdateTaskType, TaskTypeResponse
from app.crud.task_types import task_type_crud


router = APIRouter(
    prefix="/task-type",
    tags=["TaskTypes"],
    responses={404: {"description": "Task type not found"}},
)


@router.get("/", response_model=List[TaskTypeResponse])
async def list_task_types(session: AsyncSession = Depends(get_async_session), user: TaskType = Depends(get_current_admin)):
    items = await task_type_crud.get_many(session)
    return [TaskTypeResponse.model_validate(i, from_attributes=True) for i in items]


@router.post("/", response_model=TaskTypeResponse)
async def create_task_type(payload: CreateTaskType, session: AsyncSession = Depends(get_async_session), user: TaskType = Depends(get_current_admin)):
    created = await task_type_crud.create(session, payload)
    return TaskTypeResponse.model_validate(created, from_attributes=True)


@router.get("/all", response_model=List[TaskTypeResponse])
async def list_task_types_public(session: AsyncSession = Depends(get_async_session), user: TaskType = Depends(get_current_user)):
    items = await task_type_crud.get_many(session)
    return [TaskTypeResponse.model_validate(i, from_attributes=True) for i in items]


@router.get("/{task_type_id}", response_model=TaskTypeResponse)
async def get_task_type(task_type_id: int, session: AsyncSession = Depends(get_async_session), user: TaskType = Depends(get_current_admin)):
    item = await task_type_crud.get_one(session, TaskType.id == task_type_id)
    if not item:
        raise HTTPException(status_code=404, detail="Task type not found")
    return TaskTypeResponse.model_validate(item, from_attributes=True)


@router.patch("/{task_type_id}", response_model=TaskTypeResponse)
async def update_task_type(task_type_id: int, payload: UpdateTaskType, session: AsyncSession = Depends(get_async_session), user: TaskType = Depends(get_current_admin)):
    item = await task_type_crud.get_one(session, TaskType.id == task_type_id)
    if not item:
        raise HTTPException(status_code=404, detail="Task type not found")
    updated = await task_type_crud.update(session, item, payload)
    return TaskTypeResponse.model_validate(updated, from_attributes=True)


@router.delete("/{task_type_id}", status_code=status.HTTP_200_OK)
async def delete_task_type(task_type_id: int, session: AsyncSession = Depends(get_async_session), user: TaskType = Depends(get_current_admin)):
    item = await task_type_crud.get_one(session, TaskType.id == task_type_id)
    if not item:
        raise HTTPException(status_code=404, detail="Task type not found")
    await task_type_crud.delete(session, item)
    return {"message": "Task type successfully deleted"}


@router.post("/seed-defaults", status_code=status.HTTP_200_OK)
async def seed_defaults(session: AsyncSession = Depends(get_async_session), user: TaskType = Depends(get_current_admin)):
    count_result = await session.execute(select(func.count(TaskType.id)))
    tt_count = count_result.scalar_one()
    if tt_count > 0:
        return {"message": "Task types already seeded", "count": tt_count}
    seed_items = [
        ("training", "Training tasks", "other"),
        ("hr task", "Human resources related tasks", "other"),
        ("it task", "IT related tasks", "other"),
        ("admin task", "Administrative tasks", "other"),
        ("delivery assurance", "Delivery assurance tasks", "other"),
        ("sick leave", "Sick leave", "leave"),
        ("holidays", "Holidays", "leave"),
        ("vacation leave", "Vacation leave", "leave"),
        ("absent without office leave", "Absent without office leave", "leave"),
    ]
    for name, description, category in seed_items:
        session.add(TaskType(name=name, description=description, category=category))
    await session.commit()
    return {"message": "Seeded defaults", "count": len(seed_items)}
