"""
ZipRecruiter job board scraper

Based on JobSpy by speedyapply: https://github.com/speedyapply/JobSpy
Copyright (c) 2023 Cullen Watson
Licensed under MIT License. See LICENSE-JOBSPY for details.
"""

from typing import List, Optional
from urllib.parse import urlencode, quote_plus
from ..models import JobPost
from ..utils import format_location, parse_salary
from .base import BaseScraper


class ZipRecruiterScraper(BaseScraper):
    """Scraper for ZipRecruiter.com"""

    def __init__(self, proxies: Optional[List[str]] = None, use_proxies: bool = True):
        super().__init__("zip_recruiter", proxies=proxies, use_proxies=use_proxies)
        self.base_url = "https://www.ziprecruiter.com"

    def scrape(
        self,
        search_term: str,
        location: str,
        results_wanted: int = 10,
        hours_old: Optional[int] = None,
        **kwargs,
    ) -> List[JobPost]:
        """
        Scrape job postings from ZipRecruiter

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
        pages_to_scrape = (results_wanted // 20) + 1

        for page in range(pages_to_scrape):
            if len(jobs) >= results_wanted:
                break

            # Build search URL
            params = {
                "search": search_term,
                "location": location,
                "page": page + 1,
            }

            if hours_old:
                # ZipRecruiter time filter (in days)
                days = max(1, hours_old // 24)
                params["days"] = str(days)

            search_url = f"{self.base_url}/jobs-search?{urlencode(params)}"

            # Make request
            response = self.request_handler.make_request(search_url)

            if not response:
                print(f"Failed to fetch ZipRecruiter page {page + 1}")
                continue

            # Parse HTML
            soup = self.parse_html(response.text)

            # Find job cards
            job_cards = soup.find_all("article", class_="job_result")
            if not job_cards:
                job_cards = soup.find_all("div", class_="job_content")

            for card in job_cards:
                if len(jobs) >= results_wanted:
                    break

                try:
                    job = self._parse_job_card(card)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    print(f"Error parsing ZipRecruiter job card: {e}")
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
            title_elem = card.find("h2", class_="title")
            if not title_elem:
                title_elem = card.find("a", class_="job_link")

            if not title_elem:
                return None

            title_link = title_elem.find("a") if title_elem.name != "a" else title_elem
            title = title_link.get_text(strip=True) if title_link else ""
            job_url = title_link.get("href", "") if title_link else ""

            if job_url and not job_url.startswith("http"):
                job_url = f"{self.base_url}{job_url}"

            # Extract company
            company_elem = card.find("a", class_="company_name")
            if not company_elem:
                company_elem = card.find("span", class_="company")

            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Extract location
            location_elem = card.find("a", class_="company_location")
            if not location_elem:
                location_elem = card.find("span", class_="location")

            location = location_elem.get_text(strip=True) if location_elem else "Unknown"

            # Extract salary if available
            salary_elem = card.find("span", class_="salary")
            if not salary_elem:
                salary_elem = card.find("div", class_="job_salary")

            salary_info = parse_salary(salary_elem.get_text(strip=True) if salary_elem else None)

            # Extract job snippet/description
            snippet_elem = card.find("p", class_="job_snippet")
            if not snippet_elem:
                snippet_elem = card.find("div", class_="job_description")

            description = snippet_elem.get_text(strip=True) if snippet_elem else None

            # Extract date posted
            date_elem = card.find("time")
            date_posted = date_elem.get_text(strip=True) if date_elem else None

            # Extract job type
            job_type_elem = card.find("span", class_="job_type")
            job_type = None
            if job_type_elem:
                job_type_text = job_type_elem.get_text(strip=True).lower()
                if "full-time" in job_type_text or "full time" in job_type_text:
                    job_type = "full-time"
                elif "part-time" in job_type_text or "part time" in job_type_text:
                    job_type = "part-time"
                elif "contract" in job_type_text:
                    job_type = "contract"

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
                site="zip_recruiter",
                description=description,
                job_type=job_type,
                date_posted=date_posted,
                salary_min=salary_info.get("salary_min"),
                salary_max=salary_info.get("salary_max"),
                salary_currency=salary_info.get("salary_currency"),
                salary_period=salary_info.get("salary_period"),
                remote=remote,
            )

        except Exception as e:
            print(f"Error parsing ZipRecruiter job: {e}")
            return None
