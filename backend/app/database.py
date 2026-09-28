from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from contextlib import asynccontextmanager
from app.secrets import (
    DATABASE,
    DB_HOST,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
)

_pwd = f":{DB_PASSWORD}" if DB_PASSWORD else ""
DATABASE_URL = f"mysql+aiomysql://{DB_USER}{_pwd}@{DB_HOST}:{DB_PORT}/{DATABASE}"


Base = declarative_base()

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=1800,
)

async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

# Context manager for direct database operations
@asynccontextmanager
async def get_async_session_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions outside of FastAPI dependencies."""
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
