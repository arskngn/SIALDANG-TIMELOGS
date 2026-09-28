from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.system_options import SystemOption
from app.schemas.system_options import CreateSystemOption, UpdateSystemOption

async def get_options_by_category(db: AsyncSession, category: str):
    result = await db.execute(select(SystemOption).where(SystemOption.category == category))
    return result.scalars().all()

async def get_all_options(db: AsyncSession):
    result = await db.execute(select(SystemOption))
    return result.scalars().all()

async def create_option(db: AsyncSession, option: CreateSystemOption):
    db_option = SystemOption(category=option.category, value=option.value)
    db.add(db_option)
    await db.commit()
    await db.refresh(db_option)
    return db_option

async def update_option(db: AsyncSession, option_id: int, option_update: UpdateSystemOption):
    result = await db.execute(select(SystemOption).where(SystemOption.id == option_id))
    db_option = result.scalars().first()
    if db_option:
        db_option.value = option_update.value
        await db.commit()
        await db.refresh(db_option)
    return db_option

async def delete_option(db: AsyncSession, option_id: int):
    result = await db.execute(select(SystemOption).where(SystemOption.id == option_id))
    db_option = result.scalars().first()
    if db_option:
        await db.delete(db_option)
        await db.commit()
    return db_option
