"""
Structured job data models for better comparison and filtering

Organizes raw job data into logical sections for deterministic filtering
and structured LLM comparisons.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import re


@dataclass
class TitleSection:
    """Job title and role information"""
    job_title: str
    seniority_level: Optional[str] = None  # junior, mid, senior, lead, principal, director, vp, c-level
    job_family: Optional[str] = None  # engineering, payroll, marketing, etc.

    def __post_init__(self):
        """Extract seniority level and job family from title"""
        if not self.job_family:
            self.job_family = self._extract_job_family(self.job_title)

    @staticmethod
    def _extract_job_family(title: str) -> str:
        """Extract job family/function from title"""
        title_lower = title.lower()

        # Define job families and their keywords
        families = {
            'payroll': ['payroll', 'compensation'],
            'engineering': ['engineer', 'developer', 'programmer', 'software', 'devops', 'sre'],
            'data': ['data scientist', 'data engineer', 'data analyst', 'machine learning', 'ml engineer'],
            'product': ['product manager', 'product owner', 'pm'],
            'design': ['designer', 'ux', 'ui', 'design'],
            'marketing': ['marketing', 'growth', 'demand gen', 'content marketing'],
            'sales': ['sales', 'account executive', 'business development', 'bdr', 'sdr'],
            'hr': ['recruiter', 'hr', 'human resources', 'people ops', 'talent'],
            'finance': ['finance', 'accounting', 'financial analyst', 'controller', 'treasury'],
            'operations': ['operations', 'ops', 'supply chain', 'logistics'],
            'customer': ['customer success', 'customer support', 'customer service', 'account manager'],
            'legal': ['legal', 'counsel', 'attorney', 'compliance'],
            'executive': ['ceo', 'cto', 'cfo', 'coo', 'chief', 'president', 'vp'],
        }

        for family, keywords in families.items():
            if any(keyword in title_lower for keyword in keywords):
                return family

        return 'other'

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'job_title': self.job_title,
            'seniority_level': self.seniority_level,
            'job_family': self.job_family,
        }


@dataclass
class RequirementsSection:
    """Job requirements and qualifications"""
    skills: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    experience_years_min: Optional[int] = None
    experience_years_max: Optional[int] = None
    education_level: Optional[str] = None  # high school, associate, bachelor, master, phd
    certifications: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Extract structured data from requirements"""
        if not self.experience_years_min:
            self._extract_experience_years()
        if not self.education_level:
            self._extract_education_level()
        if not self.certifications:
            self._extract_certifications()

    def _extract_experience_years(self):
        """Extract years of experience from requirements"""
        # Look for patterns like "5+ years", "3-5 years", "5 years"
        pattern = r'(\d+)(?:\s*-\s*(\d+))?\s*(?:\+)?\s*years?'

        for req in self.requirements:
            match = re.search(pattern, req.lower())
            if match:
                min_years = int(match.group(1))
                max_years = int(match.group(2)) if match.group(2) else None

                self.experience_years_min = min_years
                self.experience_years_max = max_years
                break

    def _extract_education_level(self):
        """Extract education requirements"""
        all_text = ' '.join(self.requirements).lower()

        if 'phd' in all_text or 'doctorate' in all_text:
            self.education_level = 'phd'
        elif 'master' in all_text or 'mba' in all_text or "master's" in all_text:
            self.education_level = 'master'
        elif 'bachelor' in all_text or "bachelor's" in all_text or 'bs' in all_text or 'ba' in all_text:
            self.education_level = 'bachelor'
        elif 'associate' in all_text or "associate's" in all_text:
            self.education_level = 'associate'

    def _extract_certifications(self):
        """Extract certification requirements"""
        all_text = ' '.join(self.requirements).lower()

        cert_keywords = [
            'certified', 'certification', 'cpa', 'cpp', 'fpc', 'phr', 'sphr',
            'shrm-cp', 'shrm-scp', 'pmp', 'csm', 'aws', 'azure', 'gcp'
        ]

        for req in self.requirements:
            req_lower = req.lower()
            if any(keyword in req_lower for keyword in cert_keywords):
                self.certifications.append(req)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'skills': self.skills,
            'requirements': self.requirements,
            'experience_years_min': self.experience_years_min,
            'experience_years_max': self.experience_years_max,
            'education_level': self.education_level,
            'certifications': self.certifications,
        }


@dataclass
class CompensationSection:
    """Compensation and benefits information"""
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = 'USD'
    salary_period: str = 'yearly'
    benefits: List[str] = field(default_factory=list)
    has_equity: bool = False
    has_bonus: bool = False

    def __post_init__(self):
        """Extract equity and bonus flags from benefits"""
        if not self.has_equity:
            self._check_equity()
        if not self.has_bonus:
            self._check_bonus()

    def _check_equity(self):
        """Check if equity/stock options are mentioned"""
        equity_keywords = ['equity', 'stock', 'rsu', 'options', 'espp', 'shares']
        benefits_text = ' '.join(self.benefits).lower()
        self.has_equity = any(keyword in benefits_text for keyword in equity_keywords)

    def _check_bonus(self):
        """Check if bonuses are mentioned"""
        bonus_keywords = ['bonus', 'commission', 'incentive']
        benefits_text = ' '.join(self.benefits).lower()
        self.has_bonus = any(keyword in benefits_text for keyword in bonus_keywords)

    def get_salary_midpoint(self) -> Optional[float]:
        """Calculate salary midpoint"""
        if self.salary_min and self.salary_max:
            return (self.salary_min + self.salary_max) / 2
        elif self.salary_min:
            return self.salary_min
        elif self.salary_max:
            return self.salary_max
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'salary_min': self.salary_min,
            'salary_max': self.salary_max,
            'salary_currency': self.salary_currency,
            'salary_period': self.salary_period,
            'benefits': self.benefits,
            'has_equity': self.has_equity,
            'has_bonus': self.has_bonus,
            'salary_midpoint': self.get_salary_midpoint(),
        }


@dataclass
class WorkArrangementsSection:
    """Work arrangements and schedule"""
    remote: bool = False
    remote_policy: Optional[str] = None  # remote, hybrid, onsite
    location: str = 'Unknown'
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    location_country: Optional[str] = None
    job_type: Optional[str] = None  # full-time, part-time, contract, etc.
    work_schedule: Optional[str] = None
    work_arrangements: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Extract remote policy from work arrangements"""
        if not self.remote_policy:
            self._extract_remote_policy()

    def _extract_remote_policy(self):
        """Determine remote work policy"""
        if self.remote:
            self.remote_policy = 'remote'
        else:
            # Check work arrangements for hybrid mentions
            arrangements_text = ' '.join(self.work_arrangements).lower()
            location_lower = self.location.lower()

            if 'hybrid' in arrangements_text or 'hybrid' in location_lower:
                self.remote_policy = 'hybrid'
            else:
                self.remote_policy = 'onsite'

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'remote': self.remote,
            'remote_policy': self.remote_policy,
            'location': self.location,
            'location_city': self.location_city,
            'location_state': self.location_state,
            'location_country': self.location_country,
            'job_type': self.job_type,
            'work_schedule': self.work_schedule,
            'work_arrangements': self.work_arrangements,
        }


@dataclass
class CompanySection:
    """Company information"""
    company_name: str
    company_size: Optional[str] = None
    company_revenue: Optional[str] = None
    company_industry: Optional[str] = None
    company_description: Optional[str] = None
    company_website: Optional[str] = None
    company_url: Optional[str] = None

    def get_size_category(self) -> str:
        """Categorize company size"""
        if not self.company_size:
            return 'unknown'

        size_lower = self.company_size.lower()

        # Extract number range
        if 'to' in size_lower:
            parts = size_lower.split('to')
            try:
                # Get the upper bound
                upper = int(''.join(filter(str.isdigit, parts[1])))

                if upper <= 50:
                    return 'startup'
                elif upper <= 200:
                    return 'small'
                elif upper <= 1000:
                    return 'medium'
                elif upper <= 10000:
                    return 'large'
                else:
                    return 'enterprise'
            except:
                pass

        return 'unknown'

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'company_name': self.company_name,
            'company_size': self.company_size,
            'company_size_category': self.get_size_category(),
            'company_revenue': self.company_revenue,
            'company_industry': self.company_industry,
            'company_description': self.company_description,
            'company_website': self.company_website,
            'company_url': self.company_url,
        }


@dataclass
class JobComparison:
    """Complete job data organized into sections for comparison"""
    # Original job data
    job_url: str
    date_posted: Optional[str] = None
    description: Optional[str] = None

    # Structured sections
    title: Optional[TitleSection] = None
    requirements: Optional[RequirementsSection] = None
    compensation: Optional[CompensationSection] = None
    work: Optional[WorkArrangementsSection] = None
    company: Optional[CompanySection] = None

    # Raw data reference
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with all sections"""
        result = {
            'job_url': self.job_url,
            'date_posted': self.date_posted,
            'description': self.description,
        }

        if self.title:
            result['title'] = self.title.to_dict()

        if self.requirements:
            result['requirements'] = self.requirements.to_dict()

        if self.compensation:
            result['compensation'] = self.compensation.to_dict()

        if self.work:
            result['work'] = self.work.to_dict()

        if self.company:
            result['company'] = self.company.to_dict()

        return result


def extract_job_sections(job: Dict[str, Any]) -> JobComparison:
    """
    Extract structured sections from raw job data

    Args:
        job: Raw job dictionary from JobPost

    Returns:
        JobComparison object with organized sections
    """
    # Title section
    title_section = TitleSection(
        job_title=job.get('title', 'Unknown'),
    )

    # Requirements section
    requirements_section = RequirementsSection(
        skills=job.get('skills', []),
        requirements=job.get('requirements', []),
    )

    # Compensation section
    compensation_section = CompensationSection(
        salary_min=job.get('salary_min'),
        salary_max=job.get('salary_max'),
        salary_currency=job.get('salary_currency', 'USD'),
        salary_period=job.get('salary_period', 'yearly'),
        benefits=job.get('benefits', []),
    )

    # Work arrangements section
    work_section = WorkArrangementsSection(
        remote=job.get('remote', False),
        location=job.get('location', 'Unknown'),
        location_city=job.get('location_city'),
        location_state=job.get('location_state'),
        location_country=job.get('location_country_name'),
        job_type=job.get('job_type'),
        work_schedule=job.get('work_schedule'),
        work_arrangements=job.get('work_arrangements', []),
    )

    # Company section
    company_section = CompanySection(
        company_name=job.get('company', 'Unknown'),
        company_size=job.get('company_size'),
        company_revenue=job.get('company_revenue'),
        company_industry=job.get('company_industry'),
        company_description=job.get('company_description'),
        company_website=job.get('company_website'),
        company_url=job.get('company_url'),
    )

    # Create JobComparison object
    return JobComparison(
        job_url=job.get('job_url', ''),
        date_posted=job.get('date_posted'),
        description=job.get('description'),
        title=title_section,
        requirements=requirements_section,
        compensation=compensation_section,
        work=work_section,
        company=company_section,
        raw_data=job,
    )
