"""
Base scraper class for all job board scrapers

Based on JobSpy by speedyapply: https://github.com/speedyapply/JobSpy
Copyright (c) 2023 Cullen Watson
Licensed under MIT License. See LICENSE-JOBSPY.txt for details.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
import requests

from ..models import JobPost
from ..utils import RequestHandler


class BaseScraper(ABC):
    """Abstract base class for job board scrapers"""

    def __init__(
        self,
        site_name: str,
        proxies: Optional[List[str]] = None,
        use_proxies: bool = True,
    ):
        """
        Initialize the scraper

        Args:
            site_name: Name of the job board site
            proxies: List of proxy URLs to use
            use_proxies: Whether to use proxies (default: True)
        """
        self.site_name = site_name
        self.request_handler = RequestHandler(proxies=proxies, use_proxies=use_proxies)

    @abstractmethod
    def scrape(
        self,
        search_term: str,
        location: str,
        results_wanted: int = 10,
        **kwargs,
    ) -> List[JobPost]:
        """
        Scrape job postings

        Args:
            search_term: Job title or keywords to search for
            location: Geographic location for job search
            results_wanted: Number of results to retrieve
            **kwargs: Additional site-specific parameters

        Returns:
            List of JobPost objects
        """
        pass

    def parse_html(self, html_content: str) -> BeautifulSoup:
        """
        Parse HTML content using BeautifulSoup

        Args:
            html_content: HTML string to parse

        Returns:
            BeautifulSoup object
        """
        return BeautifulSoup(html_content, "lxml")

    def close(self):
        """Close the request handler session"""
        self.request_handler.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
