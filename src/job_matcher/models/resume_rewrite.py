"""
Pydantic models for resume rewriting and cover letter generation.

These models enforce strict schema validation to prevent hallucinations
and ensure no information is lost during the rewrite process.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

# Import existing models for reuse
from src.job_matcher.resume_parser import (
    ContactInfo, ExperienceEntry, EducationEntry
)


class VerificationStatus(str, Enum):
    """Verification result status"""
    PASSED = "passed"
    WARNING = "warning"  # Minor discrepancies
    FAILED = "failed"    # Information loss detected


# =============================================================================
# Rewritten Section Models
# =============================================================================

class RewrittenSummary(BaseModel):
    """Rewritten professional summary with change tracking"""
    original: str = Field(description="Original summary text")
    rewritten: str = Field(description="Rewritten summary tailored to job")
    keywords_added: List[str] = Field(default_factory=list, description="Keywords incorporated")
    changes_made: List[str] = Field(default_factory=list, description="Description of changes")


class RewrittenExperienceEntry(BaseModel):
    """Rewritten experience entry preserving all original facts"""
    # Immutable fields - these MUST NOT change
    title: str = Field(description="Original job title - DO NOT CHANGE")
    company: str = Field(description="Original company name - DO NOT CHANGE")
    start_date: str = Field(description="Original start date - DO NOT CHANGE")
    end_date: str = Field(description="Original end date - DO NOT CHANGE")
    location: str = Field(default="", description="Original location - DO NOT CHANGE")

    # Mutable fields with tracking
    original_bullets: List[str] = Field(description="Original bullet points")
    rewritten_bullets: List[str] = Field(description="Rewritten bullets with keywords")
    bullet_changes: List[str] = Field(default_factory=list, description="Changes made to each bullet")


class RewrittenSkills(BaseModel):
    """Rewritten skills section with organization tracking"""
    original_skills: List[str] = Field(description="Original skill list")
    rewritten_skills: List[str] = Field(description="Skills reordered/grouped for relevance")
    skills_highlighted: List[str] = Field(default_factory=list, description="Skills emphasized for this job")
    organization_strategy: str = Field(default="", description="How skills were organized")


class RewrittenResume(BaseModel):
    """Complete rewritten resume with change tracking"""
    # Contact info (never modified)
    contact: ContactInfo = Field(description="Original contact info - unchanged")

    # Rewritten sections
    summary: RewrittenSummary
    experience: List[RewrittenExperienceEntry]
    skills: RewrittenSkills

    # Unchanged sections (pass through)
    education: List[EducationEntry] = Field(default_factory=list, description="Education - unchanged")
    certifications: List[str] = Field(default_factory=list, description="Certifications - unchanged")
    languages: List[str] = Field(default_factory=list, description="Languages - unchanged")

    # Metadata
    target_job_title: str = Field(default="", description="Job title this resume was tailored for")
    target_company: str = Field(default="", description="Company this resume was tailored for")
    keywords_incorporated: List[str] = Field(default_factory=list, description="All keywords added")
    overall_changes: List[str] = Field(default_factory=list, description="Summary of all changes")


# =============================================================================
# Verification Models
# =============================================================================

class FactDiscrepancy(BaseModel):
    """A single discrepancy found during verification"""
    section: str = Field(description="Section where discrepancy was found")
    field: str = Field(description="Specific field with discrepancy")
    original_value: str = Field(description="Value in original resume")
    rewritten_value: str = Field(description="Value in rewritten resume")
    discrepancy_type: str = Field(description="Type: 'missing', 'modified', 'fabricated'")
    severity: str = Field(description="Severity: 'critical', 'warning', 'info'")


class SchemaVerificationResult(BaseModel):
    """Result of programmatic schema comparison"""
    passed: bool = Field(description="Whether all critical checks passed")
    discrepancies: List[FactDiscrepancy] = Field(default_factory=list)
    checks_performed: Dict[str, bool] = Field(default_factory=dict)


class LLMVerificationResult(BaseModel):
    """Result of LLM-based fact verification"""
    passed: bool = Field(description="Whether LLM confirms all facts preserved")
    confidence: float = Field(default=0.0, description="Confidence score 0-1")
    findings: List[str] = Field(default_factory=list, description="LLM findings")
    potential_issues: List[str] = Field(default_factory=list, description="Potential hallucinations detected")
    recommendation: str = Field(default="", description="LLM recommendation")


class VerificationReport(BaseModel):
    """Combined verification report from both methods"""
    status: VerificationStatus
    schema_check: SchemaVerificationResult
    llm_check: LLMVerificationResult
    overall_passed: bool = Field(description="Both checks passed")
    summary: str = Field(description="Human-readable summary")


# =============================================================================
# Cover Letter Models
# =============================================================================

class CoverLetterParagraph(BaseModel):
    """A single paragraph in the cover letter with fact citations"""
    type: str = Field(description="Type: 'opening', 'body', 'skills', 'closing'")
    content: str = Field(description="Paragraph text")
    facts_used: List[str] = Field(default_factory=list, description="Facts from resume used in this paragraph")


class CoverLetter(BaseModel):
    """Complete generated cover letter with cited facts"""
    greeting: str = Field(default="Dear Hiring Manager,", description="Salutation")
    paragraphs: List[CoverLetterParagraph] = Field(description="Cover letter body paragraphs")
    closing: str = Field(default="Sincerely,", description="Closing phrase")
    signature: str = Field(default="", description="Candidate name from resume")

    # Metadata
    target_job_title: str = Field(default="", description="Job this letter is for")
    target_company: str = Field(default="", description="Company this letter is for")
    word_count: int = Field(default=0, description="Total word count")
    facts_from_resume: List[str] = Field(default_factory=list, description="All facts used from resume")
    job_requirements_addressed: List[str] = Field(default_factory=list, description="Job requirements covered")

    def to_text(self) -> str:
        """Convert to plain text format"""
        lines = [self.greeting, ""]
        for para in self.paragraphs:
            lines.append(para.content)
            lines.append("")
        lines.append(self.closing)
        lines.append(self.signature)
        return "\n".join(lines)


# =============================================================================
# API Request/Response Models
# =============================================================================

class ResumeRewriteRequest(BaseModel):
    """Request for resume rewrite"""
    job_url: str = Field(description="URL of job to tailor resume for")
    sections_to_rewrite: List[str] = Field(
        default=["summary", "experience", "skills"],
        description="Which sections to rewrite"
    )


class ResumeRewriteResponse(BaseModel):
    """Response containing rewritten resume"""
    success: bool
    rewritten_resume: Optional[RewrittenResume] = None
    verification: Optional[VerificationReport] = None
    plain_text: Optional[str] = None
    error: Optional[str] = None


class CoverLetterRequest(BaseModel):
    """Request for cover letter generation"""
    job_url: str = Field(description="URL of job to write cover letter for")
    tone: str = Field(default="professional", description="Tone: professional, enthusiastic, formal")
    max_words: int = Field(default=400, description="Target word count")


class CoverLetterResponse(BaseModel):
    """Response containing generated cover letter"""
    success: bool
    cover_letter: Optional[CoverLetter] = None
    plain_text: Optional[str] = None
    error: Optional[str] = None
