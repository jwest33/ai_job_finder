"""
Templates API Endpoints

REST endpoints for resume and requirements management.
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import yaml
from dotenv import load_dotenv

from src.utils.profile_manager import ProfilePaths

router = APIRouter()


def get_current_profile_paths() -> ProfilePaths:
    """Get ProfilePaths for the current active profile, reloading env first."""
    # Reload .env to get the latest ACTIVE_PROFILE
    load_dotenv(override=True)
    return ProfilePaths()


class ResumeContent(BaseModel):
    """Resume content response"""
    content: str
    last_modified: Optional[str] = None


class ResumeUpdate(BaseModel):
    """Resume update request"""
    content: str


class RequirementsContent(BaseModel):
    """Requirements content response"""
    content: str
    data: Optional[dict] = None
    last_modified: Optional[str] = None


class RequirementsUpdate(BaseModel):
    """Requirements update request"""
    content: str


class ValidationResult(BaseModel):
    """Validation result for a single template"""
    valid: bool
    exists: bool
    size: Optional[int] = None
    errors: Optional[list] = None


class TemplateValidation(BaseModel):
    """Template validation response"""
    resume: ValidationResult
    requirements: ValidationResult


def get_file_info(path: Path) -> tuple[bool, Optional[int], Optional[str]]:
    """Get file existence, size, and last modified time."""
    if path.exists():
        stat = path.stat()
        return True, stat.st_size, str(stat.st_mtime)
    return False, None, None


@router.get("/resume", response_model=ResumeContent)
async def get_resume():
    """Get current resume content."""
    paths = get_current_profile_paths()
    resume_path = paths.resume_path

    if not resume_path.exists():
        raise HTTPException(status_code=404, detail="Resume file not found")

    content = resume_path.read_text(encoding='utf-8')
    exists, size, mtime = get_file_info(resume_path)

    return ResumeContent(
        content=content,
        last_modified=mtime,
    )


@router.put("/resume")
async def update_resume(update: ResumeUpdate):
    """Update resume content."""
    paths = get_current_profile_paths()
    resume_path = paths.resume_path

    # Ensure templates directory exists
    resume_path.parent.mkdir(parents=True, exist_ok=True)

    # Write content
    resume_path.write_text(update.content, encoding='utf-8')

    return {"success": True, "message": "Resume updated"}


@router.get("/requirements", response_model=RequirementsContent)
async def get_requirements():
    """Get current requirements content."""
    paths = get_current_profile_paths()
    req_path = paths.requirements_path

    if not req_path.exists():
        raise HTTPException(status_code=404, detail="Requirements file not found")

    content = req_path.read_text(encoding='utf-8')
    exists, size, mtime = get_file_info(req_path)

    # Try to parse YAML
    data = None
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        pass

    return RequirementsContent(
        content=content,
        data=data,
        last_modified=mtime,
    )


@router.put("/requirements")
async def update_requirements(update: RequirementsUpdate):
    """Update requirements content."""
    paths = get_current_profile_paths()
    req_path = paths.requirements_path

    # Validate YAML syntax
    try:
        yaml.safe_load(update.content)
    except yaml.YAMLError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid YAML syntax: {str(e)}"
        )

    # Ensure templates directory exists
    req_path.parent.mkdir(parents=True, exist_ok=True)

    # Write content
    req_path.write_text(update.content, encoding='utf-8')

    return {"success": True, "message": "Requirements updated"}


@router.post("/validate", response_model=TemplateValidation)
async def validate_templates():
    """Validate both templates."""
    paths = get_current_profile_paths()

    # Validate resume
    resume_path = paths.resume_path
    resume_exists, resume_size, _ = get_file_info(resume_path)
    resume_errors = []

    if not resume_exists:
        resume_errors.append("Resume file does not exist")
    elif resume_size == 0:
        resume_errors.append("Resume file is empty")
    elif resume_size < 100:
        resume_errors.append("Resume appears too short (< 100 bytes)")

    resume_valid = len(resume_errors) == 0

    # Validate requirements
    req_path = paths.requirements_path
    req_exists, req_size, _ = get_file_info(req_path)
    req_errors = []

    if not req_exists:
        req_errors.append("Requirements file does not exist")
    elif req_size == 0:
        req_errors.append("Requirements file is empty")
    else:
        try:
            content = req_path.read_text(encoding='utf-8')
            data = yaml.safe_load(content)

            if not isinstance(data, dict):
                req_errors.append("Requirements must be a YAML dictionary")
            else:
                # Check for recommended sections
                if 'candidate_profile' not in data:
                    req_errors.append("Missing 'candidate_profile' section (recommended)")
                if 'job_requirements' not in data:
                    req_errors.append("Missing 'job_requirements' section (recommended)")

        except yaml.YAMLError as e:
            req_errors.append(f"Invalid YAML syntax: {str(e)}")

    req_valid = len([e for e in req_errors if "recommended" not in e.lower()]) == 0

    return TemplateValidation(
        resume=ValidationResult(
            valid=resume_valid,
            exists=resume_exists,
            size=resume_size,
            errors=resume_errors if resume_errors else None,
        ),
        requirements=ValidationResult(
            valid=req_valid,
            exists=req_exists,
            size=req_size,
            errors=req_errors if req_errors else None,
        ),
    )
