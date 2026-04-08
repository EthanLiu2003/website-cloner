import pytest
from app.services.job_manager import Job, JobManager
from app.schemas.job import JobStatus


class TestJob:
    def test_initial_state(self):
        job = Job("test-123", "https://example.com")
        assert job.job_id == "test-123"
        assert job.url == "https://example.com"
        assert job.status == JobStatus.STARTED
        assert job.progress == 0
        assert job.message == ""
        assert job.error is None
        assert job.html_results == {}
        assert job.screenshot_b64 is None
        assert job.pages_found == 0
        assert job.pages_cloned == 0

    def test_update_changes_state(self):
        job = Job("test-123", "https://example.com")
        job.update(JobStatus.SCRAPING, 30, "Scraping...")
        assert job.status == JobStatus.SCRAPING
        assert job.progress == 30
        assert job.message == "Scraping..."

    def test_update_puts_event_on_queue(self):
        job = Job("test-123", "https://example.com")
        job.update(JobStatus.GENERATING, 50, "Generating...")
        event = job.event_queue.get_nowait()
        assert event["status"] == "generating"
        assert event["progress"] == 50
        assert event["message"] == "Generating..."

    def test_fail_sets_error_status(self):
        job = Job("test-123", "https://example.com")
        job.fail("Something broke")
        assert job.status == JobStatus.ERROR
        assert job.error == "Something broke"

    def test_fail_puts_error_event(self):
        job = Job("test-123", "https://example.com")
        job.fail("timeout")
        event = job.event_queue.get_nowait()
        assert event["status"] == "error"
        assert event["error"] == "timeout"

    def test_complete_sets_final_state(self):
        job = Job("test-123", "https://example.com")
        job.complete()
        assert job.status == JobStatus.COMPLETED
        assert job.progress == 100
        assert job.message == "Clone completed!"

    def test_complete_puts_event_with_result_url(self):
        job = Job("test-123", "https://example.com")
        job.complete()
        event = job.event_queue.get_nowait()
        assert event["status"] == "completed"
        assert event["result_url"] == "/api/preview/test-123"

    def test_update_includes_page_counts(self):
        job = Job("test-123", "https://example.com")
        job.pages_found = 5
        job.pages_cloned = 2
        job.update(JobStatus.SCRAPING, 40, "Working...")
        event = job.event_queue.get_nowait()
        assert event["pages_found"] == 5
        assert event["pages_cloned"] == 2


class TestJobManager:
    def test_create_returns_job(self):
        manager = JobManager()
        job = manager.create("https://example.com")
        assert isinstance(job, Job)
        assert job.url == "https://example.com"
        assert job.job_id  # non-empty

    def test_create_generates_unique_ids(self):
        manager = JobManager()
        job1 = manager.create("https://example.com")
        job2 = manager.create("https://example.com")
        assert job1.job_id != job2.job_id

    def test_get_returns_existing_job(self):
        manager = JobManager()
        job = manager.create("https://example.com")
        retrieved = manager.get(job.job_id)
        assert retrieved is job

    def test_get_returns_none_for_missing(self):
        manager = JobManager()
        assert manager.get("nonexistent") is None

    def test_stores_multiple_jobs(self):
        manager = JobManager()
        job1 = manager.create("https://a.com")
        job2 = manager.create("https://b.com")
        assert manager.get(job1.job_id).url == "https://a.com"
        assert manager.get(job2.job_id).url == "https://b.com"
