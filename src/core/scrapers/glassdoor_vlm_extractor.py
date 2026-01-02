"""
Job data extractor for VLM responses.

Parses VLM JSON output into JobPost objects compatible with the existing storage.
"""

import json
import re
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..models import JobPost

logger = logging.getLogger(__name__)


@dataclass
class PartialJobPost:
    """Partial job data extracted from listing page (before clicking into detail)."""
    title: str
    company: str
    location: str
    element_id: int  # For clicking into detail
    salary_text: Optional[str] = None
    posted_text: Optional[str] = None
    is_easy_apply: bool = False
    job_url: Optional[str] = None


@dataclass
class ExtractedJobList:
    """Result of extracting jobs from a listing page."""
    jobs: List[PartialJobPost] = field(default_factory=list)
    has_more_jobs: bool = False
    next_page_element_id: Optional[int] = None
    error: Optional[str] = None


@dataclass
class ExtractedJobDetail:
    """Result of extracting a single job's full details."""
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_period: Optional[str] = None
    job_type: Optional[str] = None
    remote: Optional[bool] = None
    benefits: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    company_rating: Optional[float] = None
    posted_date: Optional[str] = None
    error: Optional[str] = None


class JobDataExtractor:
    """Extracts and validates job data from VLM responses."""

    def __init__(self):
        self.base_url = "https://www.glassdoor.com"

    def extract_json_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from VLM response, handling markdown code blocks.

        Args:
            response: Raw VLM response text

        Returns:
            Parsed JSON dict or None if parsing fails
        """
        if not response:
            return None

        # Try to extract JSON from markdown code blocks
        code_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(code_block_pattern, response)
        if match:
            json_str = match.group(1)
        else:
            # Try to find JSON object directly
            json_pattern = r'\{[\s\S]*\}'
            match = re.search(json_pattern, response)
            if match:
                json_str = match.group(0)
            else:
                json_str = response

        try:
            return json.loads(json_str.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from VLM response: {e}")
            logger.debug(f"Response was: {response[:500]}")
            return None

    def extract_from_listing(self, vlm_response: str) -> ExtractedJobList:
        """
        Extract job listings from VLM response.

        Args:
            vlm_response: VLM's JSON response for job listing extraction

        Returns:
            ExtractedJobList with parsed jobs
        """
        result = ExtractedJobList()

        data = self.extract_json_from_response(vlm_response)
        if not data:
            result.error = "Failed to parse VLM response as JSON"
            return result

        # Extract jobs array
        jobs_data = data.get("jobs", [])
        if not isinstance(jobs_data, list):
            result.error = "Expected 'jobs' to be an array"
            return result

        for job_data in jobs_data:
            try:
                job = PartialJobPost(
                    title=job_data.get("title", "Unknown Title"),
                    company=job_data.get("company", "Unknown Company"),
                    location=job_data.get("location", ""),
                    element_id=job_data.get("element_id", 0),
                    salary_text=job_data.get("salary_text"),
                    posted_text=job_data.get("posted_text"),
                    is_easy_apply=job_data.get("is_easy_apply", False),
                )
                result.jobs.append(job)
            except Exception as e:
                logger.warning(f"Failed to parse job entry: {e}")
                continue

        result.has_more_jobs = data.get("has_more_jobs", False)
        result.next_page_element_id = data.get("next_page_element_id")

        logger.info(f"Extracted {len(result.jobs)} jobs from listing")
        return result

    def extract_from_detail(self, vlm_response: str) -> ExtractedJobDetail:
        """
        Extract full job details from VLM response.

        Args:
            vlm_response: VLM's JSON response for job detail extraction

        Returns:
            ExtractedJobDetail with parsed data
        """
        result = ExtractedJobDetail()

        data = self.extract_json_from_response(vlm_response)
        if not data:
            result.error = "Failed to parse VLM response as JSON"
            return result

        result.title = data.get("title")
        result.company = data.get("company")
        result.location = data.get("location")
        result.description = data.get("description")
        result.salary_min = self._parse_salary(data.get("salary_min"))
        result.salary_max = self._parse_salary(data.get("salary_max"))
        result.salary_period = data.get("salary_period")
        result.job_type = data.get("job_type")
        result.remote = data.get("remote")
        result.benefits = data.get("benefits", [])
        result.requirements = data.get("requirements", [])
        result.company_rating = self._parse_float(data.get("company_rating"))
        result.posted_date = data.get("posted_date")

        return result

    def merge_to_job_post(
        self,
        partial: PartialJobPost,
        detail: Optional[ExtractedJobDetail],
        job_url: str,
    ) -> JobPost:
        """
        Merge partial listing data with full detail into a JobPost.

        Args:
            partial: Partial job from listing page
            detail: Full detail from job detail page (may be None)
            job_url: URL of the job posting

        Returns:
            Complete JobPost object
        """
        # Use detail data if available, fall back to partial
        title = (detail.title if detail and detail.title else partial.title)
        company = (detail.company if detail and detail.company else partial.company)
        location = (detail.location if detail and detail.location else partial.location)

        # Parse salary from either detail or listing text
        salary_min = None
        salary_max = None
        salary_period = "yearly"

        if detail and detail.salary_min:
            salary_min = detail.salary_min
            salary_max = detail.salary_max
            salary_period = detail.salary_period or "yearly"
        elif partial.salary_text:
            salary_min, salary_max, salary_period = self._parse_salary_text(partial.salary_text)

        # Parse posted date
        date_posted = None
        if detail and detail.posted_date:
            date_posted = self._parse_posted_date(detail.posted_date)
        elif partial.posted_text:
            date_posted = self._parse_posted_date(partial.posted_text)

        # Determine remote status
        remote = False
        if detail and detail.remote is not None:
            remote = detail.remote
        elif location:
            remote = self._is_remote_location(location)

        # Parse location components
        location_city, location_state = self._parse_location(location)

        return JobPost(
            title=title,
            company=company,
            location=location or "Unknown",
            job_url=job_url,
            site="glassdoor",
            description=detail.description if detail else None,
            job_type=detail.job_type if detail else None,
            date_posted=date_posted,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency="USD",
            salary_period=salary_period,
            remote=remote,
            location_city=location_city,
            location_state=location_state,
            benefits=detail.benefits if detail else [],
            requirements=detail.requirements if detail else [],
            company_rating=detail.company_rating if detail else None,
            easy_apply=partial.is_easy_apply,
        )

    def _parse_salary(self, value: Any) -> Optional[float]:
        """Parse salary value to float."""
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                # Remove currency symbols and commas
                cleaned = re.sub(r'[^\d.]', '', value)
                return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            return None
        return None

    def _parse_float(self, value: Any) -> Optional[float]:
        """Parse any value to float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _parse_salary_text(self, text: str) -> tuple[Optional[float], Optional[float], str]:
        """
        Parse salary text like "$80K - $120K" or "$50/hr".

        Returns:
            (min_salary, max_salary, period)
        """
        if not text:
            return None, None, "yearly"

        text = text.upper()

        # Detect period
        period = "yearly"
        if "/HR" in text or "HOUR" in text:
            period = "hourly"
        elif "/MO" in text or "MONTH" in text:
            period = "monthly"

        # Extract numbers
        numbers = re.findall(r'[\d,]+(?:\.\d+)?', text.replace('K', '000'))

        if not numbers:
            return None, None, period

        # Clean and convert
        values = []
        for num in numbers:
            try:
                values.append(float(num.replace(',', '')))
            except ValueError:
                continue

        if len(values) >= 2:
            return min(values), max(values), period
        elif len(values) == 1:
            return values[0], values[0], period

        return None, None, period

    def _parse_posted_date(self, text: str) -> Optional[str]:
        """
        Parse posted date text like "2 days ago" into ISO date string.

        Returns:
            ISO date string (YYYY-MM-DD) or None
        """
        if not text:
            return None

        text = text.lower().strip()
        now = datetime.now()

        # Handle "just now", "today"
        if "just" in text or "now" in text or text == "today":
            return str(now.date())

        # Handle "yesterday"
        if "yesterday" in text:
            return str((now - timedelta(days=1)).date())

        # Handle "X days/hours/minutes ago"
        match = re.search(r'(\d+)\s*(d|day|h|hour|m|min|w|week)', text)
        if match:
            value = int(match.group(1))
            unit = match.group(2)[0]

            if unit == 'd':
                delta = timedelta(days=value)
            elif unit == 'h':
                delta = timedelta(hours=value)
            elif unit == 'm':
                delta = timedelta(minutes=value)
            elif unit == 'w':
                delta = timedelta(weeks=value)
            else:
                delta = timedelta(days=0)

            return str((now - delta).date())

        # Handle "30+" format (days)
        match = re.search(r'(\d+)\+', text)
        if match:
            days = int(match.group(1))
            return str((now - timedelta(days=days)).date())

        return None

    def _parse_location(self, location: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse location into city and state components.

        Returns:
            (city, state)
        """
        if not location:
            return None, None

        # Handle "Remote" locations
        if location.lower() in ("remote", "remote, us", "remote - us"):
            return None, None

        # Try "City, State" format
        if ", " in location:
            parts = location.split(", ")
            city = parts[0].strip() if parts else None
            state = parts[1].strip() if len(parts) > 1 else None
            return city, state

        return location, None

    def _is_remote_location(self, location: str) -> bool:
        """Check if location indicates remote work."""
        if not location:
            return False
        location_lower = location.lower()
        return any(term in location_lower for term in ["remote", "work from home", "wfh", "anywhere"])
