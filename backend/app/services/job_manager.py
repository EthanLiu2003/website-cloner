import uuid
import asyncio
from typing import Dict, Optional
from ..schemas.job import JobStatus


class Job:
    def __init__(self, job_id: str, url: str):
        self.job_id = job_id
        self.url = url
        self.status = JobStatus.STARTED
        self.progress = 0
        self.message = ""
        self.error = None
        self.html_results: Dict[str, str] = {}  # url -> html for multi-page
        self.screenshot_b64: Optional[str] = None
        self.pages_found = 0
        self.pages_cloned = 0
        self.event_queue: asyncio.Queue = asyncio.Queue()

    def update(self, status: JobStatus, progress: int, message: str = ""):
        self.status = status
        self.progress = progress
        self.message = message
        self.event_queue.put_nowait({
            "status": status.value,
            "progress": progress,
            "message": message,
            "pages_found": self.pages_found,
            "pages_cloned": self.pages_cloned,
        })

    def fail(self, error: str):
        self.status = JobStatus.ERROR
        self.error = error
        self.event_queue.put_nowait({"status": "error", "error": error})

    def complete(self):
        self.status = JobStatus.COMPLETED
        self.progress = 100
        self.message = "Clone completed!"
        self.event_queue.put_nowait({
            "status": "completed",
            "progress": 100,
            "message": "Clone completed!",
            "result_url": f"/api/preview/{self.job_id}",
        })


class JobManager:
    def __init__(self):
        self.jobs: Dict[str, Job] = {}

    def create(self, url: str) -> Job:
        job_id = str(uuid.uuid4())
        job = Job(job_id, url)
        self.jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)


job_manager = JobManager()
