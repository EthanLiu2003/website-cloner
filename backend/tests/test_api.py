"""Integration tests for the FastAPI endpoints."""

import base64
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.job_manager import Job, JobManager, job_manager
from app.schemas.job import JobStatus


@pytest.fixture
def manager():
    """Fresh JobManager patched into both the module and router."""
    m = JobManager()
    with patch("app.routers.clone.job_manager", m), \
         patch("app.routers.clone.scraper_service") as mock_scraper, \
         patch("app.routers.clone.generator_service") as mock_generator:
        mock_scraper.scrape = AsyncMock(return_value={
            "title": "Test",
            "screenshot_b64": "abc",
            "design_context": {},
            "image_analysis": {},
            "downloaded_images": {},
        })
        mock_generator.generate_clone = AsyncMock(return_value="<h1>Cloned</h1>")
        yield m


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- Health endpoints ---

class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_root(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Website Cloner API running"

    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "api_key_configured" in data


# --- Clone endpoints ---

class TestCloneEndpoint:
    @pytest.mark.asyncio
    async def test_start_clone_returns_job_id(self, client, manager):
        resp = await client.post("/api/clone", json={"url": "https://example.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "started"

    @pytest.mark.asyncio
    async def test_start_clone_rejects_invalid_url(self, client, manager):
        resp = await client.post("/api/clone", json={"url": "ftp://bad.com"})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_start_clone_rejects_private_ip(self, client, manager):
        resp = await client.post("/api/clone", json={"url": "http://192.168.1.1"})
        assert resp.status_code == 422


# --- Status endpoint ---

class TestStatusEndpoint:
    @pytest.mark.asyncio
    async def test_status_returns_job_state(self, client, manager):
        job = manager.create("https://example.com")
        job.update(JobStatus.SCRAPING, 30, "Working...")

        resp = await client.get(f"/api/status/{job.job_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "scraping"
        assert data["progress"] == 30

    @pytest.mark.asyncio
    async def test_status_404_for_missing_job(self, client, manager):
        resp = await client.get("/api/status/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_status_includes_result_url_when_completed(self, client, manager):
        job = manager.create("https://example.com")
        job.html_results["https://example.com"] = "<h1>Done</h1>"
        job.complete()

        resp = await client.get(f"/api/status/{job.job_id}")
        data = resp.json()
        assert data["status"] == "completed"
        assert f"/api/preview/{job.job_id}" in data["result_url"]

    @pytest.mark.asyncio
    async def test_status_includes_error_on_failure(self, client, manager):
        job = manager.create("https://example.com")
        job.fail("Timed out")

        resp = await client.get(f"/api/status/{job.job_id}")
        data = resp.json()
        assert data["status"] == "error"
        assert data["error"] == "Timed out"


# --- Preview endpoint ---

class TestPreviewEndpoint:
    @pytest.mark.asyncio
    async def test_preview_returns_html(self, client, manager):
        job = manager.create("https://example.com")
        job.html_results["https://example.com"] = "<h1>Cloned Site</h1>"

        resp = await client.get(f"/api/preview/{job.job_id}")
        assert resp.status_code == 200
        assert "<h1>Cloned Site</h1>" in resp.text

    @pytest.mark.asyncio
    async def test_preview_404_for_missing_job(self, client, manager):
        resp = await client.get("/api/preview/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_preview_404_for_empty_results(self, client, manager):
        job = manager.create("https://example.com")
        resp = await client.get(f"/api/preview/{job.job_id}")
        assert resp.status_code == 404


# --- Screenshot endpoint ---

class TestScreenshotEndpoint:
    @pytest.mark.asyncio
    async def test_screenshot_returns_jpeg(self, client, manager):
        job = manager.create("https://example.com")
        # Store a tiny valid base64 string
        job.screenshot_b64 = base64.b64encode(b"\xff\xd8\xff\xe0").decode()

        resp = await client.get(f"/api/preview/{job.job_id}/screenshot")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"

    @pytest.mark.asyncio
    async def test_screenshot_404_when_missing(self, client, manager):
        job = manager.create("https://example.com")
        resp = await client.get(f"/api/preview/{job.job_id}/screenshot")
        assert resp.status_code == 404


# --- Pages endpoint ---

class TestPagesEndpoint:
    @pytest.mark.asyncio
    async def test_list_pages(self, client, manager):
        job = manager.create("https://example.com")
        job.html_results["https://example.com"] = "<h1>Home</h1>"
        job.html_results["https://example.com/about"] = "<h1>About</h1>"

        resp = await client.get(f"/api/preview/{job.job_id}/pages")
        assert resp.status_code == 200
        pages = resp.json()["pages"]
        assert len(pages) == 2
        assert "https://example.com" in pages
        assert "https://example.com/about" in pages

    @pytest.mark.asyncio
    async def test_list_pages_empty(self, client, manager):
        job = manager.create("https://example.com")
        resp = await client.get(f"/api/preview/{job.job_id}/pages")
        assert resp.status_code == 200
        assert resp.json()["pages"] == []

    @pytest.mark.asyncio
    async def test_list_pages_404_for_missing_job(self, client, manager):
        resp = await client.get("/api/preview/nonexistent/pages")
        assert resp.status_code == 404
