from pydantic import BaseModel, field_validator
from ipaddress import ip_address
from urllib.parse import urlparse


class CloneRequest(BaseModel):
    url: str
    crawl: bool = False  # Enable multi-page cloning
    max_depth: int = 2
    max_pages: int = 10

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        try:
            parsed = urlparse(v)
            if parsed.scheme not in ("http", "https"):
                raise ValueError("URL must use http or https")
            host = parsed.hostname
            if host:
                try:
                    ip = ip_address(host)
                    if ip.is_private:
                        raise ValueError("Private IPs are not allowed")
                except ValueError:
                    pass  # hostname, not IP -- that's fine
        except Exception as e:
            raise ValueError(f"Invalid URL: {e}")
        return v
