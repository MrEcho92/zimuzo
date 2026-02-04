from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(scope="session", autouse=True)
def mock_everything():
    """Mock all external dependencies"""
    with (
        patch("app.database.db.create_async_engine"),
        patch("app.database.db.sessionmaker"),
        patch("app.database.db.Base", MagicMock()),
        patch("app.database.db.get_db"),
    ):
        yield


def test_health():
    """Test health check endpoint"""
    # Import after mocking
    from starlette.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
