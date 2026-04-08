import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.services.job_manager import JobManager, job_manager


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def fresh_job_manager():
    """Return a clean JobManager and patch the global singleton."""
    manager = JobManager()
    with patch("app.services.job_manager.job_manager", manager), \
         patch("app.routers.clone.job_manager", manager):
        yield manager


@pytest.fixture
async def client():
    """Async test client that bypasses the lifespan (no real browser)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
