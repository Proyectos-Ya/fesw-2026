from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=True)

async_session_maker = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

async def create_db_and_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)