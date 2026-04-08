from pydantic import BaseModel
from typing import Optional
from enum import Enum


class JobStatus(str, Enum):
    STARTED = "started"
    SCRAPING = "scraping"
    CRAWLING = "crawling"
    GENERATING = "generating"
    COMPLETED = "completed"
    ERROR = "error"


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = 0
    message: str = ""
    error: Optional[str] = None
    result_url: Optional[str] = None
    pages_found: int = 0
    pages_cloned: int = 0
