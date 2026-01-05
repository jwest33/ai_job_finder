"""
Documents API Endpoints

REST endpoints for resume rewriting and cover letter generation.
"""

import asyncio
import json
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
    RewrittenResume, VerificationReport
)

logger = logging.getLogger(__name__)


# =============================================================================
# Tailored Document Storage
# =============================================================================

class TailoredDocumentResponse(BaseModel):
    """Response for saved tailored document."""
    found: bool
    document_type: Optional[str] = None
    plain_text: Optional[str] = None
    structured_data: Optional[dict] = None
    verification_data: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CoverLetterTemplateRequest(BaseModel):
    """Request to upload a cover letter template."""
    content: str


def _save_tailored_document(
    job_url: str,
    document_type: str,
    plain_text: str,
    structured_data: Optional[dict] = None,
    verification_data: Optional[dict] = None,
) -> bool:
    """Save a tailored document to the database."""
    db = get_profile_database()
    try:
        db.execute("""
            INSERT INTO tailored_documents (job_url, document_type, plain_text, structured_data, verification_data, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (job_url, document_type) DO UPDATE SET
                plain_text = EXCLUDED.plain_text,
                structured_data = EXCLUDED.structured_data,
                verification_data = EXCLUDED.verification_data,
                updated_at = CURRENT_TIMESTAMP
        """, (
            job_url,
            document_type,
            plain_text,
            json.dumps(structured_data) if structured_data else None,
            json.dumps(verification_data) if verification_data else None,
        ))
        return True
    except Exception as e:
        logger.exception(f"Failed to save tailored document: {e}")
        return False


def _get_tailored_document(job_url: str, document_type: str) -> Optional[dict]:
    """Get a saved tailored document from the database."""
    db = get_profile_database()
    result = db.fetchone("""
        SELECT plain_text, structured_data, verification_data, created_at, updated_at
        FROM tailored_documents
        WHERE job_url = ? AND document_type = ?
    """, (job_url, document_type))

    if not result:
        return None

    return {
        "plain_text": result[0],
        "structured_data": json.loads(result[1]) if result[1] else None,
        "verification_data": json.loads(result[2]) if result[2] else None,
        "created_at": str(result[3]) if result[3] else None,
        "updated_at": str(result[4]) if result[4] else None,
    }


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

    # Get analysis data if available (stored in jobs table)
    analysis_result = db.fetchone("""
        SELECT match_score, gap_analysis, match_explanation
        FROM jobs
        WHERE job_url = ?
    """, (job_url,))

    if analysis_result:
        job["match_score"] = analysis_result[0]
        # gap_analysis is stored as JSON text with {strengths, gaps, red_flags, assessment}
        gap_analysis_text = analysis_result[1]
        if gap_analysis_text:
            try:
                gap_data = json.loads(gap_analysis_text)
                job["strengths"] = gap_data.get("strengths", [])
                job["gaps"] = gap_data.get("gaps", [])
                job["assessment"] = gap_data.get("assessment", "")
            except (json.JSONDecodeError, TypeError):
                # Fallback if gap_analysis is plain text
                job["strengths"] = []
                job["gaps"] = []
                job["assessment"] = gap_analysis_text
        else:
            job["strengths"] = []
            job["gaps"] = []
            job["assessment"] = analysis_result[2] or ""  # Use match_explanation as fallback

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

        # Auto-save the tailored resume
        _save_tailored_document(
            job_url=decoded_url,
            document_type="resume",
            plain_text=plain_text,
            structured_data=rewritten.model_dump() if rewritten else None,
            verification_data=result.model_dump() if result else None,
        )

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

        # Load cover letter template if available
        template = None
        paths = get_current_profile_paths()
        template_path = paths.templates_dir / "cover_letter_template.txt"
        if template_path.exists():
            try:
                template = template_path.read_text(encoding='utf-8')
                logger.info("Using cover letter template")
            except Exception as e:
                logger.warning(f"Failed to load cover letter template: {e}")

        # Generate cover letter
        generator = CoverLetterGenerator()
        cover_letter = generator.generate(
            parsed,
            job,
            gap_analysis,
            tone=request.tone,
            max_words=request.max_words,
            template=template,
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

        plain_text = cover_letter.to_text()

        # Auto-save the cover letter
        _save_tailored_document(
            job_url=decoded_url,
            document_type="cover_letter",
            plain_text=plain_text,
            structured_data=cover_letter.model_dump() if cover_letter else None,
        )

        return CoverLetterResponse(
            success=True,
            cover_letter=cover_letter,
            plain_text=plain_text,
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


# =============================================================================
# Tailored Documents Endpoints
# =============================================================================

@router.get("/tailored/{document_type}/{job_url:path}", response_model=TailoredDocumentResponse)
async def get_tailored_document(document_type: str, job_url: str):
    """
    Get a saved tailored document (resume or cover letter) for a job.

    Args:
        document_type: Either 'resume' or 'cover_letter'
        job_url: URL-encoded job URL
    """
    if document_type not in ('resume', 'cover_letter'):
        raise HTTPException(status_code=400, detail="document_type must be 'resume' or 'cover_letter'")

    decoded_url = unquote(job_url)
    doc = _get_tailored_document(decoded_url, document_type)

    if not doc:
        return TailoredDocumentResponse(found=False)

    return TailoredDocumentResponse(
        found=True,
        document_type=document_type,
        plain_text=doc["plain_text"],
        structured_data=doc["structured_data"],
        verification_data=doc["verification_data"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@router.delete("/tailored/{document_type}/{job_url:path}")
async def delete_tailored_document(document_type: str, job_url: str):
    """Delete a saved tailored document to allow regeneration."""
    if document_type not in ('resume', 'cover_letter'):
        raise HTTPException(status_code=400, detail="document_type must be 'resume' or 'cover_letter'")

    decoded_url = unquote(job_url)
    db = get_profile_database()

    try:
        db.execute("""
            DELETE FROM tailored_documents
            WHERE job_url = ? AND document_type = ?
        """, (decoded_url, document_type))
        return {"success": True, "message": f"Deleted {document_type} for job"}
    except Exception as e:
        logger.exception(f"Failed to delete tailored document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/cover-letter/template")
async def upload_cover_letter_template(request: CoverLetterTemplateRequest):
    """
    Upload a cover letter template to use as a base for generation.

    The template will be saved to the profile's templates directory.
    """
    paths = get_current_profile_paths()
    template_path = paths.templates_dir / "cover_letter_template.txt"

    try:
        template_path.write_text(request.content, encoding='utf-8')
        return {"success": True, "message": "Cover letter template saved", "path": str(template_path)}
    except Exception as e:
        logger.exception(f"Failed to save cover letter template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cover-letter/template")
async def get_cover_letter_template():
    """Get the saved cover letter template if it exists."""
    paths = get_current_profile_paths()
    template_path = paths.templates_dir / "cover_letter_template.txt"

    if not template_path.exists():
        return {"found": False, "content": None}

    try:
        content = template_path.read_text(encoding='utf-8')
        return {"found": True, "content": content}
    except Exception as e:
        logger.exception(f"Failed to read cover letter template: {e}")
        raise HTTPException(status_code=500, detail=str(e))
