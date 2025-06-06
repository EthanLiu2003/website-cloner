# app/__init__.py

from .main import app
from .scraper import WebScraper

__version__ = "0.1.0"
__all__ = ["app", "WebScraper"]
