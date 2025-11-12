import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# TODO: echo=False to disable SQL echoing for production
engine = create_async_engine(str(settings.get_database_url), echo=False, future=True)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Create Base class for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session"""
    logging.info("Creating a new database session")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
