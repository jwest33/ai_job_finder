"""
Job board scrapers

Note: Indeed and Glassdoor scrapers are implemented with GraphQL APIs.
GlassdoorVLMScraper uses visual automation via OmniParser + VLM.
LinkedIn and ZipRecruiter scrapers are disabled until they are updated
to use proper APIs instead of HTML scraping.
"""

from .base import BaseScraper
from .indeed import IndeedScraper
from .glassdoor import GlassdoorScraper

# VLM-powered scraper (optional, requires VLM agent project)
try:
    from .glassdoor_vlm import GlassdoorVLMScraper
except ImportError:
    GlassdoorVLMScraper = None

# Disabled scrapers (need GraphQL/API implementation):
# from .linkedin import LinkedInScraper
# from .ziprecruiter import ZipRecruiterScraper

__all__ = [
    "BaseScraper",
    "IndeedScraper",
    "GlassdoorScraper",
    "GlassdoorVLMScraper",
    # "LinkedInScraper",
    # "ZipRecruiterScraper",
]
