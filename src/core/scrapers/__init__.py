"""
Job board scrapers

Note: Indeed and Glassdoor scrapers are implemented with GraphQL APIs.
LinkedIn and ZipRecruiter scrapers are disabled until they are updated
to use proper APIs instead of HTML scraping.
"""

from .base import BaseScraper
from .indeed import IndeedScraper
from .glassdoor import GlassdoorScraper

# Disabled scrapers (need GraphQL/API implementation):
# from .linkedin import LinkedInScraper
# from .ziprecruiter import ZipRecruiterScraper

__all__ = [
    "BaseScraper",
    "IndeedScraper",
    "GlassdoorScraper",
    # "LinkedInScraper",
    # "ZipRecruiterScraper",
]
