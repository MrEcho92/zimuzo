import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.database.db import Base, get_db
from app.main import app


@pytest.mark.skip(reason="This test is currently broken and needs fixing")
async def test_db():
    """Create test database"""
    DATABASE_URL = (
        "postgresql+asyncpg://emailapp:emailapp_test_password@localhost:5432/emailapp_test_db"
    )
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    yield async_session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def client(test_db):
    """Create test client"""

    async def override_get_db():
        async with test_db() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def test_health(client):
    """Test health check endpoint"""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
