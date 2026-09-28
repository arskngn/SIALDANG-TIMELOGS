from typing import List, Optional, Type, TypeVar, Generic

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
ORMModel = TypeVar("ORMModel",bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)
OwnerIDType = int


class CRUDRepository(Generic[ORMModel]):
    """Base interface for CRUD operations."""

    def __init__(self,model: Type[ORMModel]) -> None:
        """Initialize the CRUD repository."""
        self._model = model
        self._name = model.__name__

    async def get_one(self, session: AsyncSession, *args) -> Optional[ORMModel]:
        """Retrieve one record."""
        stmt = select(self._model).where(*args)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_many(self, session: AsyncSession,*args) -> List[ORMModel]:
        """Retrieve multiple records with pagination."""
        stmt = (select(self._model).where(*args))
        result = await session.execute(stmt)
        return result.scalars().all()

    async def create(self, session: AsyncSession, obj_create: CreateSchemaType) -> ORMModel:
        """Create a new record."""
        obj_data = obj_create.model_dump(exclude_none=True, exclude_unset=False)
        db_obj = self._model(**obj_data)
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def update(
        self,session: AsyncSession,db_obj: ORMModel,obj_update: UpdateSchemaType) -> ORMModel:
        """Update a record."""
        update_data = obj_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def delete(self, session: AsyncSession, db_obj: ORMModel) -> ORMModel:
        """Delete a record."""
        await session.delete(db_obj)
        await session.commit()
        return db_obj

    async def create_with_owner(
        self,
        db: AsyncSession,
        obj_create: CreateSchemaType,
        owner_id: OwnerIDType,
    ) -> ORMModel:
        """Create a new record with owner ID."""
        obj_data = obj_create.model_dump(
            exclude_none=True, exclude_unset=True, exclude_defaults=True
        )
        db_obj = self._model(**obj_data, owner_id=owner_id)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_many_for_owner(
        self,
        db: AsyncSession,
        *args,
        owner_id: OwnerIDType,
        skip: int = 0,
        limit: int = 100,
        **kwargs
    ) -> List[ORMModel]:
        """Retrieve many records for a specific owner."""
        return await self.get_many(
            db, *args, skip=skip, limit=limit, owner_id=owner_id, **kwargs
        )
