"""
LinkedIn job board scraper

Based on JobSpy by speedyapply: https://github.com/speedyapply/JobSpy
Copyright (c) 2023 Cullen Watson
Licensed under MIT License. See LICENSE-JOBSPY.txt for details.
"""

from typing import List, Optional
from urllib.parse import urlencode
from ..models import JobPost
from ..utils import format_location, parse_salary
from .base import BaseScraper


class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn.com jobs"""

    def __init__(self, proxies: Optional[List[str]] = None, use_proxies: bool = True):
        super().__init__("linkedin", proxies=proxies, use_proxies=use_proxies)
        self.base_url = "https://www.linkedin.com"

    def scrape(
        self,
        search_term: str,
        location: str,
        results_wanted: int = 10,
        hours_old: Optional[int] = None,
        **kwargs,
    ) -> List[JobPost]:
        """
        Scrape job postings from LinkedIn

        Args:
            search_term: Job title or keywords
            location: Geographic location
            results_wanted: Number of results to retrieve
            hours_old: Filter jobs posted within X hours
            **kwargs: Additional parameters

        Returns:
            List of JobPost objects
        """
        jobs = []
        pages_to_scrape = min((results_wanted // 25) + 1, 4)  # LinkedIn is restrictive

        for page in range(pages_to_scrape):
            if len(jobs) >= results_wanted:
                break

            # Build search URL
            params = {
                "keywords": search_term,
                "location": location,
                "start": page * 25,
            }

            if hours_old:
                # LinkedIn time filter: r86400 = 24h, r604800 = 7d, r2592000 = 30d
                if hours_old <= 24:
                    params["f_TPR"] = "r86400"
                elif hours_old <= 168:  # 7 days
                    params["f_TPR"] = "r604800"
                else:
                    params["f_TPR"] = "r2592000"

            search_url = f"{self.base_url}/jobs/search?{urlencode(params)}"

            # Make request with additional headers for LinkedIn
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }

            response = self.request_handler.make_request(search_url, headers=headers)

            if not response:
                print(f"Failed to fetch LinkedIn page {page + 1}")
                continue

            # Parse HTML
            soup = self.parse_html(response.text)

            # Find job cards
            job_cards = soup.find_all("div", class_="base-card")
            if not job_cards:
                job_cards = soup.find_all("li", class_="jobs-search__results-list")

            for card in job_cards:
                if len(jobs) >= results_wanted:
                    break

                try:
                    job = self._parse_job_card(card)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    print(f"Error parsing LinkedIn job card: {e}")
                    continue

        return jobs[:results_wanted]

    def _parse_job_card(self, card) -> Optional[JobPost]:
        """
        Parse a single job card element

        Args:
            card: BeautifulSoup element for job card

        Returns:
            JobPost object or None
        """
        try:
            # Extract title and URL
            title_elem = card.find("h3", class_="base-search-card__title")
            if not title_elem:
                title_elem = card.find("a", class_="job-card-list__title")

            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)

            # Get job URL
            link_elem = card.find("a", class_="base-card__full-link")
            if not link_elem:
                link_elem = card.find("a")

            job_url = link_elem.get("href", "") if link_elem else ""
            if job_url and not job_url.startswith("http"):
                job_url = f"{self.base_url}{job_url}"

            # Extract company
            company_elem = card.find("h4", class_="base-search-card__subtitle")
            if not company_elem:
                company_elem = card.find("a", class_="job-card-container__company-name")

            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Extract location
            location_elem = card.find("span", class_="job-search-card__location")
            location = location_elem.get_text(strip=True) if location_elem else "Unknown"

            # Extract salary if available (LinkedIn rarely shows this)
            salary_elem = card.find("span", class_="job-search-card__salary-info")
            salary_info = parse_salary(salary_elem.get_text(strip=True) if salary_elem else None)

            # Extract date posted
            date_elem = card.find("time", class_="job-search-card__listdate")
            date_posted = date_elem.get("datetime", None) if date_elem else None

            # Check if remote
            remote = False
            if location_elem:
                loc_text = location_elem.get_text(strip=True).lower()
                remote = "remote" in loc_text

            return JobPost(
                title=title,
                company=company,
                location=location,
                job_url=job_url,
                site="linkedin",
                date_posted=date_posted,
                salary_min=salary_info.get("salary_min"),
                salary_max=salary_info.get("salary_max"),
                salary_currency=salary_info.get("salary_currency"),
                salary_period=salary_info.get("salary_period"),
                remote=remote,
            )

        except Exception as e:
            print(f"Error parsing LinkedIn job: {e}")
            return None
