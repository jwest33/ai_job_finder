"""
Documents API Endpoints

REST endpoints for resume rewriting and cover letter generation.
"""

import asyncio
import logging
from typing import Optional
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from src.core.database import get_database
from src.utils.profile_manager import ProfilePaths
from src.job_matcher.resume_parser import ResumeParser
from src.job_matcher.resume_rewriter import ResumeRewriter
from src.job_matcher.information_verifier import InformationVerifier
from src.job_matcher.cover_letter_generator import CoverLetterGenerator
from src.job_matcher.models.resume_rewrite import (
    ResumeRewriteRequest, ResumeRewriteResponse,
    CoverLetterRequest, CoverLetterResponse,
    RewrittenResume
)

logger = logging.getLogger(__name__)
router = APIRouter()


def get_profile_database():
    """Get database for the current active profile."""
    load_dotenv(override=True)
    return get_database()


def get_current_profile_paths() -> ProfilePaths:
    """Get ProfilePaths for the current active profile."""
    load_dotenv(override=True)
    return ProfilePaths()


def _load_resume_text() -> Optional[str]:
    """Load resume text from profile."""
    paths = get_current_profile_paths()
    if paths.resume_path.exists():
        return paths.resume_path.read_text(encoding='utf-8')
    return None


def _load_job(job_url: str) -> Optional[dict]:
    """Load job from database with analysis data."""
    db = get_profile_database()

    # Get job data
    job_result = db.fetchone("""
        SELECT job_url, title, company, description, location, remote,
               skills, requirements, salary_min, salary_max
        FROM jobs
        WHERE job_url = ?
    """, (job_url,))

    if not job_result:
        return None

    # skills and requirements are VARCHAR[] arrays in DuckDB, returned as lists
    skills = job_result[6]
    if isinstance(skills, str):
        skills = skills.split(",") if skills else []
    elif skills is None:
        skills = []

    requirements = job_result[7]
    if isinstance(requirements, str):
        requirements = requirements.split("\n") if requirements else []
    elif requirements is None:
        requirements = []

    job = {
        "job_url": job_result[0],
        "title": job_result[1],
        "company": job_result[2],
        "description": job_result[3],
        "location": job_result[4],
        "remote": job_result[5],
        "skills": skills,
        "requirements": requirements,
        "salary_min": job_result[8],
        "salary_max": job_result[9],
    }

    # Get analysis data if available
    analysis_result = db.fetchone("""
        SELECT match_score, strengths, gaps, assessment
        FROM job_analysis
        WHERE job_url = ?
    """, (job_url,))

    if analysis_result:
        job["match_score"] = analysis_result[0]
        job["strengths"] = analysis_result[1].split("\n") if analysis_result[1] else []
        job["gaps"] = analysis_result[2].split("\n") if analysis_result[2] else []
        job["assessment"] = analysis_result[3]

    return job


def _serialize_rewritten_resume(resume: RewrittenResume) -> str:
    """Serialize rewritten resume to plain text."""
    lines = []

    # Contact
    lines.append(resume.contact.name)
    contact_parts = [resume.contact.email, resume.contact.phone, resume.contact.location]
    contact_line = " | ".join(filter(None, contact_parts))
    if contact_line:
        lines.append(contact_line)
    if resume.contact.linkedin:
        lines.append(resume.contact.linkedin)
    lines.append("")

    # Summary
    if resume.summary.rewritten:
        lines.append(resume.summary.rewritten)
        lines.append("")

    # Experience
    lines.append("EXPERIENCE")
    lines.append("")
    for exp in resume.experience:
        header = f"{exp.title} | {exp.company} | {exp.start_date} - {exp.end_date}"
        if exp.location:
            header += f" | {exp.location}"
        lines.append(header)
        for bullet in exp.rewritten_bullets:
            lines.append(f"  - {bullet}")
        lines.append("")

    # Skills
    lines.append("SKILLS")
    lines.append("")
    lines.append(", ".join(resume.skills.rewritten_skills))
    lines.append("")

    # Education
    if resume.education:
        lines.append("EDUCATION")
        lines.append("")
        for edu in resume.education:
            edu_line = f"{edu.degree}, {edu.school}"
            if edu.year:
                edu_line += f", {edu.year}"
            lines.append(edu_line)
            if edu.gpa:
                lines.append(f"  GPA: {edu.gpa}")
            if edu.honors:
                lines.append(f"  {edu.honors}")
        lines.append("")

    # Certifications
    if resume.certifications:
        lines.append("CERTIFICATIONS")
        lines.append("")
        for cert in resume.certifications:
            lines.append(f"  - {cert}")
        lines.append("")

    # Languages
    if resume.languages:
        lines.append("LANGUAGES")
        lines.append("")
        lines.append(", ".join(resume.languages))

    return "\n".join(lines).strip()


# =============================================================================
# Resume Rewrite Endpoints
# =============================================================================

@router.post("/resume/rewrite", response_model=ResumeRewriteResponse)
async def rewrite_resume(request: ResumeRewriteRequest):
    """
    Rewrite resume sections tailored for a specific job.

    Performs section-by-section rewriting with dual verification:
    1. Schema diff to ensure no information loss
    2. LLM verification for semantic fact preservation

    Returns the rewritten resume with verification report.
    """
    decoded_url = unquote(request.job_url)
    logger.info(f"Resume rewrite request for job: {decoded_url}")

    # Load resume
    resume_text = _load_resume_text()
    if not resume_text:
        raise HTTPException(status_code=404, detail="Resume not found in current profile")

    # Load job
    job = _load_job(decoded_url)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    def _do_rewrite():
        # Parse resume
        parser = ResumeParser()
        if not parser.test_connection():
            return None, None, "AI provider not available"

        parsed = parser.parse(resume_text)
        if not parsed:
            return None, None, "Failed to parse resume"

        # Prepare gap analysis if available
        gap_analysis = None
        if job.get("strengths") or job.get("gaps"):
            gap_analysis = {
                "strengths": job.get("strengths", []),
                "gaps": job.get("gaps", []),
                "assessment": job.get("assessment", ""),
                "keywords": job.get("skills", [])[:10],
            }

        # Rewrite resume
        rewriter = ResumeRewriter()
        rewritten = rewriter.rewrite_for_job(parsed, job, gap_analysis)
        if not rewritten:
            return parsed, None, "Failed to rewrite resume"

        # Verify no information loss
        verifier = InformationVerifier()
        verification = verifier.verify(parsed, rewritten)

        return parsed, rewritten, verification

    try:
        parsed, rewritten, result = await asyncio.to_thread(_do_rewrite)

        if isinstance(result, str):
            # Error message
            return ResumeRewriteResponse(
                success=False,
                error=result,
            )

        # Serialize to plain text
        plain_text = _serialize_rewritten_resume(rewritten)

        return ResumeRewriteResponse(
            success=True,
            rewritten_resume=rewritten,
            verification=result,
            plain_text=plain_text,
        )

    except Exception as e:
        logger.exception(f"Resume rewrite error: {e}")
        return ResumeRewriteResponse(
            success=False,
            error=str(e),
        )


# =============================================================================
# Cover Letter Endpoints
# =============================================================================

@router.post("/cover-letter/generate", response_model=CoverLetterResponse)
async def generate_cover_letter(request: CoverLetterRequest):
    """
    Generate a cover letter for a specific job.

    Uses only facts from the resume to prevent hallucinations.
    Each paragraph cites which resume facts it uses.
    """
    decoded_url = unquote(request.job_url)
    logger.info(f"Cover letter generation request for job: {decoded_url}")

    # Load resume
    resume_text = _load_resume_text()
    if not resume_text:
        raise HTTPException(status_code=404, detail="Resume not found in current profile")

    # Load job
    job = _load_job(decoded_url)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    def _do_generate():
        # Parse resume
        parser = ResumeParser()
        if not parser.test_connection():
            return None, "AI provider not available"

        parsed = parser.parse(resume_text)
        if not parsed:
            return None, "Failed to parse resume"

        # Prepare gap analysis if available
        gap_analysis = None
        if job.get("strengths") or job.get("gaps"):
            gap_analysis = {
                "strengths": job.get("strengths", []),
                "gaps": job.get("gaps", []),
            }

        # Generate cover letter
        generator = CoverLetterGenerator()
        cover_letter = generator.generate(
            parsed,
            job,
            gap_analysis,
            tone=request.tone,
            max_words=request.max_words,
        )

        return cover_letter, None

    try:
        cover_letter, error = await asyncio.to_thread(_do_generate)

        if error:
            return CoverLetterResponse(success=False, error=error)

        if not cover_letter:
            return CoverLetterResponse(
                success=False,
                error="Failed to generate cover letter"
            )

        return CoverLetterResponse(
            success=True,
            cover_letter=cover_letter,
            plain_text=cover_letter.to_text(),
        )

    except Exception as e:
        logger.exception(f"Cover letter generation error: {e}")
        return CoverLetterResponse(success=False, error=str(e))


class SaveCoverLetterRequest(BaseModel):
    """Request to save cover letter content."""
    content: str


@router.post("/cover-letter/{job_url:path}/save")
async def save_cover_letter(job_url: str, request: SaveCoverLetterRequest):
    """Save generated cover letter to database for a job."""
    decoded_url = unquote(job_url)

    db = get_profile_database()

    # Check if job exists
    job = _load_job(decoded_url)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Update job_applications table
    try:
        db.execute("""
            INSERT INTO job_applications (job_url, cover_letter, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (job_url) DO UPDATE SET
                cover_letter = EXCLUDED.cover_letter,
                updated_at = CURRENT_TIMESTAMP
        """, (decoded_url, request.content))

        return {"success": True, "message": "Cover letter saved"}
    except Exception as e:
        logger.exception(f"Failed to save cover letter: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")


@router.get("/cover-letter/{job_url:path}")
async def get_saved_cover_letter(job_url: str):
    """Get saved cover letter for a job."""
    decoded_url = unquote(job_url)

    db = get_profile_database()

    result = db.fetchone("""
        SELECT cover_letter, updated_at
        FROM job_applications
        WHERE job_url = ?
    """, (decoded_url,))

    if not result or not result[0]:
        return {"found": False, "content": None}

    return {
        "found": True,
        "content": result[0],
        "updated_at": str(result[1]) if result[1] else None,
    }
