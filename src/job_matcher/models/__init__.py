"""
Job matching models and data structures
"""

from .job_sections import (
    TitleSection,
    RequirementsSection,
    CompensationSection,
    WorkArrangementsSection,
    CompanySection,
    JobComparison,
    extract_job_sections,
)

__all__ = [
    "TitleSection",
    "RequirementsSection",
    "CompensationSection",
    "WorkArrangementsSection",
    "CompanySection",
    "JobComparison",
    "extract_job_sections",
]
