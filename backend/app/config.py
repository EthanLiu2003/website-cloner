from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    cors_origins: str = "http://localhost:3000"
    scrape_timeout: int = 30
    ai_timeout: int = 180
    max_tokens: int = 16000
    ai_model: str = "claude-sonnet-4-20250514"
    browser_pool_size: int = 3
    max_crawl_depth: int = 2
    max_crawl_pages: int = 10

    # Image download settings
    enable_image_download: bool = True
    max_image_size_bytes: int = 500_000
    max_total_image_bytes: int = 5_000_000
    max_image_count: int = 15
    image_download_timeout: int = 8

    class Config:
        env_file = ".env"


settings = Settings()
