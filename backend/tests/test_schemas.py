import pytest
from pydantic import ValidationError
from app.schemas.clone import CloneRequest
from app.schemas.job import JobStatus, JobResponse


class TestCloneRequest:
    def test_valid_https_url(self):
        req = CloneRequest(url="https://example.com")
        assert req.url == "https://example.com"

    def test_valid_http_url(self):
        req = CloneRequest(url="http://example.com")
        assert req.url == "http://example.com"

    def test_defaults(self):
        req = CloneRequest(url="https://example.com")
        assert req.crawl is False
        assert req.max_depth == 2
        assert req.max_pages == 10

    def test_custom_crawl_options(self):
        req = CloneRequest(url="https://example.com", crawl=True, max_depth=3, max_pages=5)
        assert req.crawl is True
        assert req.max_depth == 3
        assert req.max_pages == 5

    def test_rejects_ftp_scheme(self):
        with pytest.raises(ValidationError, match="http or https"):
            CloneRequest(url="ftp://example.com/file")

    def test_rejects_private_ip(self):
        with pytest.raises(ValidationError, match="Private IPs"):
            CloneRequest(url="http://192.168.1.1")

    def test_rejects_localhost_ip(self):
        with pytest.raises(ValidationError, match="Private IPs"):
            CloneRequest(url="http://127.0.0.1")

    def test_allows_public_ip(self):
        req = CloneRequest(url="http://93.184.216.34")
        assert req.url == "http://93.184.216.34"

    def test_allows_domain_name(self):
        req = CloneRequest(url="https://www.google.com/search?q=test")
        assert "google.com" in req.url

    def test_rejects_no_scheme(self):
        with pytest.raises(ValidationError):
            CloneRequest(url="example.com")


class TestJobStatus:
    def test_all_statuses_exist(self):
        assert JobStatus.STARTED == "started"
        assert JobStatus.SCRAPING == "scraping"
        assert JobStatus.CRAWLING == "crawling"
        assert JobStatus.GENERATING == "generating"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.ERROR == "error"

    def test_string_enum_values(self):
        assert JobStatus.STARTED.value == "started"
        assert isinstance(JobStatus.STARTED, str)


class TestJobResponse:
    def test_minimal_response(self):
        resp = JobResponse(job_id="abc", status=JobStatus.STARTED)
        assert resp.job_id == "abc"
        assert resp.progress == 0
        assert resp.error is None
        assert resp.result_url is None

    def test_full_response(self):
        resp = JobResponse(
            job_id="abc",
            status=JobStatus.COMPLETED,
            progress=100,
            message="Done",
            result_url="/api/preview/abc",
            pages_found=3,
            pages_cloned=3,
        )
        assert resp.pages_found == 3
