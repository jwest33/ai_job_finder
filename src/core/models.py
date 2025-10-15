"""
Data models for job postings
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class JobType(Enum):
    FULL_TIME = "full-time"
    PART_TIME = "part-time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    OTHER = "other"


class Site(Enum):
    INDEED = "indeed"
    LINKEDIN = "linkedin"
    ZIP_RECRUITER = "zip_recruiter"
    GLASSDOOR = "glassdoor"


@dataclass
class JobPost:
    """Model for a job posting with comprehensive Indeed GraphQL data"""

    # Core fields (original)
    title: str
    company: str
    location: str
    job_url: str
    site: str
    description: Optional[str] = None
    job_type: Optional[str] = None
    date_posted: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    salary_period: Optional[str] = None
    company_url: Optional[str] = None
    company_industry: Optional[str] = None
    remote: Optional[bool] = False

    # Phase 2: Rich Attributes (skills, requirements, benefits)
    skills: Optional[List[str]] = field(default_factory=list)
    requirements: Optional[List[str]] = field(default_factory=list)
    benefits: Optional[List[str]] = field(default_factory=list)
    work_arrangements: Optional[List[str]] = field(default_factory=list)

    # Phase 3: Enhanced Location Data
    location_country_code: Optional[str] = None
    location_country_name: Optional[str] = None
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    location_postal_code: Optional[str] = None

    # Phase 4: Company Enrichment
    company_size: Optional[str] = None
    company_revenue: Optional[str] = None
    company_description: Optional[str] = None
    company_ceo: Optional[str] = None
    company_website: Optional[str] = None
    company_logo_url: Optional[str] = None
    company_header_image_url: Optional[str] = None

    # Phase 5: Advanced Fields
    work_schedule: Optional[str] = None
    detailed_salary: Optional[str] = None
    source_site: Optional[str] = None
    tracking_key: Optional[str] = None
    date_on_site: Optional[str] = None

    # Phase 6: Glassdoor-Specific Fields
    glassdoor_listing_id: Optional[int] = None
    glassdoor_tracking_key: Optional[str] = None
    glassdoor_job_link: Optional[str] = None
    easy_apply: Optional[bool] = None
    occupation_code: Optional[str] = None
    occupation_id: Optional[int] = None
    occupation_confidence: Optional[float] = None
    company_full_name: Optional[str] = None
    company_short_name: Optional[str] = None
    company_division: Optional[str] = None
    company_rating: Optional[float] = None
    company_glassdoor_id: Optional[int] = None
    salary_source: Optional[str] = None
    is_sponsored: Optional[bool] = None
    sponsorship_level: Optional[str] = None
    location_id: Optional[int] = None
    location_country_id: Optional[int] = None

    def to_dict(self):
        """Convert JobPost to dictionary"""
        return {
            # Core fields
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "job_url": self.job_url,
            "site": self.site,
            "description": self.description,
            "job_type": self.job_type,
            "date_posted": self.date_posted,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_currency": self.salary_currency,
            "salary_period": self.salary_period,
            "company_url": self.company_url,
            "company_industry": self.company_industry,
            "remote": self.remote,

            # Phase 2: Attributes
            "skills": self.skills,
            "requirements": self.requirements,
            "benefits": self.benefits,
            "work_arrangements": self.work_arrangements,

            # Phase 3: Location
            "location_country_code": self.location_country_code,
            "location_country_name": self.location_country_name,
            "location_city": self.location_city,
            "location_state": self.location_state,
            "location_postal_code": self.location_postal_code,

            # Phase 4: Company
            "company_size": self.company_size,
            "company_revenue": self.company_revenue,
            "company_description": self.company_description,
            "company_ceo": self.company_ceo,
            "company_website": self.company_website,
            "company_logo_url": self.company_logo_url,
            "company_header_image_url": self.company_header_image_url,

            # Phase 5: Advanced
            "work_schedule": self.work_schedule,
            "detailed_salary": self.detailed_salary,
            "source_site": self.source_site,
            "tracking_key": self.tracking_key,
            "date_on_site": self.date_on_site,

            # Phase 6: Glassdoor-Specific
            "glassdoor_listing_id": self.glassdoor_listing_id,
            "glassdoor_tracking_key": self.glassdoor_tracking_key,
            "glassdoor_job_link": self.glassdoor_job_link,
            "easy_apply": self.easy_apply,
            "occupation_code": self.occupation_code,
            "occupation_id": self.occupation_id,
            "occupation_confidence": self.occupation_confidence,
            "company_full_name": self.company_full_name,
            "company_short_name": self.company_short_name,
            "company_division": self.company_division,
            "company_rating": self.company_rating,
            "company_glassdoor_id": self.company_glassdoor_id,
            "salary_source": self.salary_source,
            "is_sponsored": self.is_sponsored,
            "sponsorship_level": self.sponsorship_level,
            "location_id": self.location_id,
            "location_country_id": self.location_country_id,
        }
