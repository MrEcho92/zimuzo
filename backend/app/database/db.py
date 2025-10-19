import logging
from typing import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# TODO: echo=False to disable SQL echoing for production
engine = create_async_engine(str(settings.get_database_url), echo=False, future=True)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Create Base class for models
class Base(DeclarativeBase):
    metadata = MetaData()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session"""
    logging.info("Creating a new database session")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        # Import models to ensure they're registered
        from app.models.models import APIKey, User  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)
