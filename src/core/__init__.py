"""
core - A Python library for web scraping job postings from multiple job boards
"""

from .scraper import scrape_jobs
from .database import DatabaseManager, get_database
from .storage import JobStorage

__version__ = "0.1.0"
__all__ = ["scrape_jobs", "DatabaseManager", "get_database", "JobStorage"]
