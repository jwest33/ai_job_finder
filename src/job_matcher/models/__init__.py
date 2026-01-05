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

from .resume_rewrite import (
    VerificationStatus,
    RewrittenSummary,
    RewrittenExperienceEntry,
    RewrittenSkills,
    RewrittenResume,
    FactDiscrepancy,
    SchemaVerificationResult,
    LLMVerificationResult,
    VerificationReport,
    CoverLetterParagraph,
    CoverLetter,
    ResumeRewriteRequest,
    ResumeRewriteResponse,
    CoverLetterRequest,
    CoverLetterResponse,
)

__all__ = [
    # Job sections
    "TitleSection",
    "RequirementsSection",
    "CompensationSection",
    "WorkArrangementsSection",
    "CompanySection",
    "JobComparison",
    "extract_job_sections",
    # Resume rewrite
    "VerificationStatus",
    "RewrittenSummary",
    "RewrittenExperienceEntry",
    "RewrittenSkills",
    "RewrittenResume",
    "FactDiscrepancy",
    "SchemaVerificationResult",
    "LLMVerificationResult",
    "VerificationReport",
    "CoverLetterParagraph",
    "CoverLetter",
    "ResumeRewriteRequest",
    "ResumeRewriteResponse",
    "CoverLetterRequest",
    "CoverLetterResponse",
]
