"""
Deterministic job filters for pre-screening

Fast, rule-based filters that eliminate irrelevant jobs before AI scoring.
Reduces AI API calls by 50-70% and improves overall processing speed.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv
from .models.job_sections import extract_job_sections, JobComparison

load_dotenv()


class JobFilters:
    """Deterministic filters for job pre-screening"""

    def __init__(self, candidate_requirements: Dict[str, Any], preferences: Dict[str, Any]):
        """
        Initialize JobFilters

        Args:
            candidate_requirements: Candidate requirements from YAML
            preferences: Job preferences from YAML
        """
        self.requirements = candidate_requirements
        self.preferences = preferences

        # Load filter configuration from .env
        self.enable_title_filter = os.getenv('FILTER_TITLE_ENABLED', 'true').lower() == 'true'
        self.enable_salary_filter = os.getenv('FILTER_SALARY_ENABLED', 'true').lower() == 'true'
        self.enable_location_filter = os.getenv('FILTER_LOCATION_ENABLED', 'true').lower() == 'true'
        self.enable_remote_filter = os.getenv('FILTER_REMOTE_ENABLED', 'true').lower() == 'true'
        self.enable_job_type_filter = os.getenv('FILTER_JOB_TYPE_ENABLED', 'true').lower() == 'true'
        self.enable_company_size_filter = os.getenv('FILTER_COMPANY_SIZE_ENABLED', 'false').lower() == 'true'
        self.enable_posting_age_filter = os.getenv('FILTER_POSTING_AGE_ENABLED', 'true').lower() == 'true'

        # Get max job age from preferences (default: 30 days)
        self.max_job_age_days = self.preferences.get('max_job_age_days', 30)

        # Pre-computed title keywords (built on demand)
        self._title_keywords = None
        self._title_exclude_keywords = None

    def _precompute_title_keywords(self):
        """Pre-compute title keywords once instead of per-job."""
        if self._title_keywords is not None:
            return  # Already computed

        # Get excluded keywords
        self._title_exclude_keywords = [k.lower() for k in self.requirements.get('title_exclude_keywords', [])]

        # Build all keywords from target roles and related keywords
        target_titles = self.requirements.get('target_roles', [])
        related_keywords = self.requirements.get('related_keywords', [])

        all_keywords = []
        for title in target_titles:
            words = title.lower().split()
            all_keywords.extend(words)
        all_keywords.extend([k.lower() for k in related_keywords])

        # Remove duplicates and stop words
        stop_words = {'and', 'or', 'the', 'a', 'an', 'for', 'to', 'of', 'in', 'with'}
        self._title_keywords = [k for k in set(all_keywords) if k not in stop_words]

    def apply_all_filters(self, job: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Apply all enabled filters to a job

        Args:
            job: Raw job dictionary

        Returns:
            Tuple of (passes_filters: bool, rejection_reasons: List[str])
        """
        rejection_reasons = []

        # Extract structured sections
        job_sections = extract_job_sections(job)

        # Apply each filter
        if self.enable_title_filter:
            passes, reason = self.filter_title(job_sections)
            if not passes:
                rejection_reasons.append(reason)

        if self.enable_salary_filter:
            passes, reason = self.filter_salary(job_sections)
            if not passes:
                rejection_reasons.append(reason)

        if self.enable_location_filter:
            passes, reason = self.filter_location(job_sections)
            if not passes:
                rejection_reasons.append(reason)

        if self.enable_remote_filter:
            passes, reason = self.filter_remote(job_sections)
            if not passes:
                rejection_reasons.append(reason)

        if self.enable_job_type_filter:
            passes, reason = self.filter_job_type(job_sections)
            if not passes:
                rejection_reasons.append(reason)

        if self.enable_company_size_filter:
            passes, reason = self.filter_company_size(job_sections)
            if not passes:
                rejection_reasons.append(reason)

        if self.enable_posting_age_filter:
            passes, reason = self.filter_posting_age(job_sections)
            if not passes:
                rejection_reasons.append(reason)

        # Job passes if no rejection reasons
        passes_all = len(rejection_reasons) == 0

        return passes_all, rejection_reasons

    def filter_title(self, job: JobComparison) -> Tuple[bool, Optional[str]]:
        """
        Filter by job title relevance

        Checks if title contains target keywords or matches excluded patterns.
        Uses precomputed keywords for speed if available.

        Returns:
            Tuple of (passes: bool, rejection_reason: Optional[str])
        """
        if not job.title:
            return True, None

        title_lower = job.title.job_title.lower()

        # Use precomputed keywords if available, otherwise compute on-demand
        if self._title_exclude_keywords is not None:
            exclude_keywords = self._title_exclude_keywords
        else:
            exclude_keywords = [k.lower() for k in self.requirements.get('title_exclude_keywords', [])]

        # Check excluded keywords first
        for keyword in exclude_keywords:
            if keyword in title_lower:
                return False, f"Title contains excluded keyword: '{keyword}'"

        # Use precomputed keywords if available
        if self._title_keywords is not None:
            all_keywords = self._title_keywords
        else:
            # Fallback: compute on-demand
            target_titles = self.requirements.get('target_roles', [])
            related_keywords = self.requirements.get('related_keywords', [])
            all_keywords = []
            for title in target_titles:
                all_keywords.extend(title.lower().split())
            all_keywords.extend([k.lower() for k in related_keywords])
            stop_words = {'and', 'or', 'the', 'a', 'an', 'for', 'to', 'of', 'in', 'with'}
            all_keywords = [k for k in set(all_keywords) if k not in stop_words]

        # If no keywords defined, pass all
        if not all_keywords:
            return True, None

        # Check if any keyword matches
        for keyword in all_keywords:
            if keyword in title_lower:
                return True, None

        return False, "Title does not match any target keywords"

    def filter_salary(self, job: JobComparison) -> Tuple[bool, Optional[str]]:
        """
        Filter by salary requirements

        Checks if job salary meets minimum requirements

        Returns:
            Tuple of (passes: bool, rejection_reason: Optional[str])
        """
        if not job.compensation:
            # If no salary info, pass through (will be evaluated by AI)
            return True, None

        min_salary_required = self.preferences.get('min_salary')
        max_salary_required = self.preferences.get('max_salary')

        if not min_salary_required:
            return True, None

        # Get job salary
        job_salary_max = job.compensation.salary_max
        job_salary_min = job.compensation.salary_min

        # If no salary info available, pass through
        if not job_salary_max and not job_salary_min:
            return True, None

        # Check if max salary meets minimum requirement
        if job_salary_max:
            if job_salary_max < min_salary_required:
                return False, f"Salary max (${job_salary_max:,.0f}) below minimum (${min_salary_required:,.0f})"

        # Check if salary range is within acceptable bounds
        if max_salary_required and job_salary_min:
            if job_salary_min > max_salary_required:
                return False, f"Salary min (${job_salary_min:,.0f}) above maximum (${max_salary_required:,.0f})"

        return True, None

    def filter_location(self, job: JobComparison) -> Tuple[bool, Optional[str]]:
        """
        Filter by location preferences

        Checks if job location matches preferred locations

        Returns:
            Tuple of (passes: bool, rejection_reason: Optional[str])
        """
        if not job.work:
            return True, None

        # If remote job, location doesn't matter
        if job.work.remote:
            return True, None

        preferred_locations = self.preferences.get('locations', [])

        # If no preferences, pass all
        if not preferred_locations:
            return True, None

        job_location = job.work.location.lower()

        # Check if any preferred location matches
        for location in preferred_locations:
            if location.lower() in job_location:
                return True, None

        return False, f"Location '{job.work.location}' not in preferred locations"

    def filter_remote(self, job: JobComparison) -> Tuple[bool, Optional[str]]:
        """
        Filter by remote work requirement

        Checks if job meets remote work requirements

        Returns:
            Tuple of (passes: bool, rejection_reason: Optional[str])
        """
        if not job.work:
            return True, None

        remote_required = self.preferences.get('remote_only', False)

        # If remote not required, pass all
        if not remote_required:
            return True, None

        # Check if job is remote
        if not job.work.remote:
            # Also check if location mentions remote
            location_lower = job.work.location.lower()
            if 'remote' not in location_lower:
                return False, "Remote work required but job is not remote"

        return True, None

    def filter_job_type(self, job: JobComparison) -> Tuple[bool, Optional[str]]:
        """
        Filter by job type (full-time, contract, etc.)

        Returns:
            Tuple of (passes: bool, rejection_reason: Optional[str])
        """
        if not job.work:
            return True, None

        preferred_types = self.preferences.get('job_types', [])

        # If no preferences, pass all
        if not preferred_types:
            return True, None

        job_type = job.work.job_type

        # If job type not specified, pass through
        if not job_type:
            return True, None

        # Normalize job type
        job_type_lower = job_type.lower().replace('-', '').replace(' ', '')

        # Check if job type matches any preferred type
        for pref_type in preferred_types:
            pref_type_normalized = pref_type.lower().replace('-', '').replace(' ', '')
            if job_type_lower == pref_type_normalized or pref_type_normalized in job_type_lower:
                return True, None

        return False, f"Job type '{job_type}' not in preferred types"

    def filter_company_size(self, job: JobComparison) -> Tuple[bool, Optional[str]]:
        """
        Filter by company size preference

        Returns:
            Tuple of (passes: bool, rejection_reason: Optional[str])
        """
        if not job.company:
            return True, None

        preferred_sizes = self.requirements.get('company_sizes', [])

        # If no preferences, pass all
        if not preferred_sizes:
            return True, None

        company_size_category = job.company.get_size_category()

        # If size not known, pass through
        if company_size_category == 'unknown':
            return True, None

        # Check if company size matches any preferred size
        for size in preferred_sizes:
            if size.lower() == company_size_category.lower():
                return True, None

        return False, f"Company size '{company_size_category}' not in preferred sizes"

    def filter_posting_age(self, job: JobComparison) -> Tuple[bool, Optional[str]]:
        """
        Filter by job posting age

        Checks if job was posted within acceptable timeframe

        Returns:
            Tuple of (passes: bool, rejection_reason: Optional[str])
        """
        if not job.date_posted:
            # If no posting date, pass through (AI will evaluate)
            return True, None

        try:
            # Parse date_posted (format: YYYY-MM-DD)
            posted_date = datetime.strptime(job.date_posted, '%Y-%m-%d')
            today = datetime.now()

            # Calculate age in days
            age_days = (today - posted_date).days

            # Check if job is too old
            if age_days > self.max_job_age_days:
                return False, f"Job posted {age_days} days ago (max: {self.max_job_age_days} days)"

            return True, None

        except (ValueError, TypeError) as e:
            # If date parsing fails, pass through
            return True, None

    def get_filter_stats(self) -> Dict[str, bool]:
        """
        Get current filter configuration

        Returns:
            Dictionary of filter names and enabled status
        """
        return {
            'title_filter': self.enable_title_filter,
            'salary_filter': self.enable_salary_filter,
            'location_filter': self.enable_location_filter,
            'remote_filter': self.enable_remote_filter,
            'job_type_filter': self.enable_job_type_filter,
            'company_size_filter': self.enable_company_size_filter,
            'posting_age_filter': self.enable_posting_age_filter,
        }


def apply_filters_to_jobs(
    jobs: List[Dict[str, Any]],
    candidate_requirements: Dict[str, Any],
    preferences: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
    """
    Apply deterministic filters to a batch of jobs (parallelized for speed)

    Args:
        jobs: List of raw job dictionaries
        candidate_requirements: Candidate requirements from YAML
        preferences: Job preferences from YAML

    Returns:
        Tuple of (
            passed_jobs: List of jobs that passed all filters,
            rejected_jobs: List of jobs that were filtered out,
            stats: Dictionary with filter statistics
        )
    """
    from concurrent.futures import ThreadPoolExecutor
    import threading

    filters = JobFilters(candidate_requirements, preferences)

    # Pre-compute keywords once (avoid rebuilding per job)
    filters._precompute_title_keywords()

    passed_jobs = []
    rejected_jobs = []
    rejection_stats = {}
    lock = threading.Lock()

    def filter_single_job(job):
        """Filter a single job - thread safe."""
        passes, reasons = filters.apply_all_filters(job)
        return job, passes, reasons

    # Use thread pool for parallel filtering
    num_workers = min(8, len(jobs))

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        results = list(executor.map(filter_single_job, jobs))

    # Process results (single-threaded to maintain order)
    for job, passes, reasons in results:
        if passes:
            passed_jobs.append(job)
        else:
            job_with_reasons = {**job, 'filter_rejection_reasons': reasons}
            rejected_jobs.append(job_with_reasons)

            for reason in reasons:
                filter_type = reason.split(':')[0] if ':' in reason else reason.split(' ')[0]
                rejection_stats[filter_type] = rejection_stats.get(filter_type, 0) + 1

    # Build statistics
    stats = {
        'total_jobs': len(jobs),
        'passed_jobs': len(passed_jobs),
        'rejected_jobs': len(rejected_jobs),
        'pass_rate': len(passed_jobs) / len(jobs) if jobs else 0,
        'rejection_reasons': rejection_stats,
    }

    return passed_jobs, rejected_jobs, stats
