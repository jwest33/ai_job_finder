"""
Settings API - Manage prompt configurations and LLM parameters.

Provides endpoints for:
- Viewing and editing system prompts
- Adjusting LLM parameters (temperature, max_tokens, etc.)
- Resetting to defaults
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.job_matcher.prompt_config import (
    PromptConfigManager,
    PromptConfig,
    ResumeRewriterConfig,
    CoverLetterConfig,
    VerificationConfig,
    LLMParameters,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


# =============================================================================
# Request/Response Models
# =============================================================================

class LLMParametersUpdate(BaseModel):
    """Update model for LLM parameters."""
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=256, le=16384)
    max_retries: Optional[int] = Field(None, ge=1, le=10)


class ResumeRewriterUpdate(BaseModel):
    """Update model for resume rewriter config."""
    system_prompt: Optional[str] = None
    parameters: Optional[LLMParametersUpdate] = None
    max_keywords: Optional[int] = Field(None, ge=1, le=25)
    summary_instructions: Optional[str] = None
    experience_instructions: Optional[str] = None
    skills_instructions: Optional[str] = None


class CoverLetterUpdate(BaseModel):
    """Update model for cover letter config."""
    system_prompt: Optional[str] = None
    parameters: Optional[LLMParametersUpdate] = None
    default_tone: Optional[str] = None
    default_max_words: Optional[int] = Field(None, ge=200, le=800)
    opening_instructions: Optional[str] = None
    body_instructions: Optional[str] = None
    closing_instructions: Optional[str] = None


class VerificationUpdate(BaseModel):
    """Update model for verification config."""
    enabled: Optional[bool] = None
    llm_verification_prompt: Optional[str] = None
    parameters: Optional[LLMParametersUpdate] = None


class PromptConfigResponse(BaseModel):
    """Response model for prompt config."""
    version: str
    updated_at: Optional[str]
    resume_rewriter: Dict[str, Any]
    cover_letter: Dict[str, Any]
    verification: Dict[str, Any]


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/prompts", response_model=PromptConfigResponse)
async def get_prompt_config():
    """Get the current prompt configuration for the active profile."""
    try:
        manager = PromptConfigManager()
        config = manager.load()
        return PromptConfigResponse(
            version=config.version,
            updated_at=config.updated_at,
            resume_rewriter=config.resume_rewriter.model_dump(),
            cover_letter=config.cover_letter.model_dump(),
            verification=config.verification.model_dump(),
        )
    except Exception as e:
        logger.exception(f"Failed to get prompt config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/prompts/resume-rewriter")
async def update_resume_rewriter_config(update: ResumeRewriterUpdate):
    """Update resume rewriter configuration."""
    try:
        manager = PromptConfigManager()
        config = manager.load()

        # Apply updates
        if update.system_prompt is not None:
            config.resume_rewriter.system_prompt = update.system_prompt
        if update.max_keywords is not None:
            config.resume_rewriter.max_keywords = update.max_keywords
        if update.summary_instructions is not None:
            config.resume_rewriter.summary_instructions = update.summary_instructions
        if update.experience_instructions is not None:
            config.resume_rewriter.experience_instructions = update.experience_instructions
        if update.skills_instructions is not None:
            config.resume_rewriter.skills_instructions = update.skills_instructions

        # Apply parameter updates
        if update.parameters:
            if update.parameters.temperature is not None:
                config.resume_rewriter.parameters.temperature = update.parameters.temperature
            if update.parameters.max_tokens is not None:
                config.resume_rewriter.parameters.max_tokens = update.parameters.max_tokens
            if update.parameters.max_retries is not None:
                config.resume_rewriter.parameters.max_retries = update.parameters.max_retries

        manager.save(config)

        return {
            "success": True,
            "message": "Resume rewriter config updated",
            "config": config.resume_rewriter.model_dump(),
        }
    except Exception as e:
        logger.exception(f"Failed to update resume rewriter config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/prompts/cover-letter")
async def update_cover_letter_config(update: CoverLetterUpdate):
    """Update cover letter configuration."""
    try:
        manager = PromptConfigManager()
        config = manager.load()

        # Apply updates
        if update.system_prompt is not None:
            config.cover_letter.system_prompt = update.system_prompt
        if update.default_tone is not None:
            config.cover_letter.default_tone = update.default_tone
        if update.default_max_words is not None:
            config.cover_letter.default_max_words = update.default_max_words
        if update.opening_instructions is not None:
            config.cover_letter.opening_instructions = update.opening_instructions
        if update.body_instructions is not None:
            config.cover_letter.body_instructions = update.body_instructions
        if update.closing_instructions is not None:
            config.cover_letter.closing_instructions = update.closing_instructions

        # Apply parameter updates
        if update.parameters:
            if update.parameters.temperature is not None:
                config.cover_letter.parameters.temperature = update.parameters.temperature
            if update.parameters.max_tokens is not None:
                config.cover_letter.parameters.max_tokens = update.parameters.max_tokens
            if update.parameters.max_retries is not None:
                config.cover_letter.parameters.max_retries = update.parameters.max_retries

        manager.save(config)

        return {
            "success": True,
            "message": "Cover letter config updated",
            "config": config.cover_letter.model_dump(),
        }
    except Exception as e:
        logger.exception(f"Failed to update cover letter config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/prompts/verification")
async def update_verification_config(update: VerificationUpdate):
    """Update verification configuration."""
    try:
        manager = PromptConfigManager()
        config = manager.load()

        # Apply updates
        if update.enabled is not None:
            config.verification.enabled = update.enabled
        if update.llm_verification_prompt is not None:
            config.verification.llm_verification_prompt = update.llm_verification_prompt

        # Apply parameter updates
        if update.parameters:
            if update.parameters.temperature is not None:
                config.verification.parameters.temperature = update.parameters.temperature
            if update.parameters.max_tokens is not None:
                config.verification.parameters.max_tokens = update.parameters.max_tokens
            if update.parameters.max_retries is not None:
                config.verification.parameters.max_retries = update.parameters.max_retries

        manager.save(config)

        return {
            "success": True,
            "message": "Verification config updated",
            "config": config.verification.model_dump(),
        }
    except Exception as e:
        logger.exception(f"Failed to update verification config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prompts/reset")
async def reset_prompt_config():
    """Reset prompt configuration to defaults."""
    try:
        manager = PromptConfigManager()
        config = manager.reset_to_defaults()

        return {
            "success": True,
            "message": "Prompt configuration reset to defaults",
            "config": {
                "version": config.version,
                "updated_at": config.updated_at,
            },
        }
    except Exception as e:
        logger.exception(f"Failed to reset prompt config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prompts/defaults")
async def get_default_prompts():
    """Get the default prompt configuration (for reference/reset preview)."""
    default_config = PromptConfig()
    return {
        "resume_rewriter": default_config.resume_rewriter.model_dump(),
        "cover_letter": default_config.cover_letter.model_dump(),
        "verification": default_config.verification.model_dump(),
    }


# =============================================================================
# Tracing Endpoints
# =============================================================================

from src.job_matcher.llm_tracer import get_tracer


@router.get("/traces")
async def get_traces(limit: int = 20, operation: Optional[str] = None, failed_only: bool = False):
    """Get recent LLM traces for debugging."""
    tracer = get_tracer()

    if failed_only:
        traces = tracer.get_failed_traces(limit)
    elif operation:
        traces = tracer.get_traces_by_operation(operation, limit)
    else:
        traces = tracer.get_recent_traces(limit)

    return {
        "traces": traces,
        "stats": tracer.get_stats(),
    }


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    """Get a specific trace by ID."""
    tracer = get_tracer()
    trace = tracer.get_trace_by_id(trace_id)

    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    return trace


@router.delete("/traces")
async def clear_traces():
    """Clear all stored traces."""
    tracer = get_tracer()
    tracer.clear_traces()
    return {"success": True, "message": "All traces cleared"}


@router.get("/traces/stats")
async def get_trace_stats():
    """Get tracing statistics."""
    tracer = get_tracer()
    return tracer.get_stats()


@router.put("/traces/enabled")
async def set_tracing_enabled(enabled: bool):
    """Enable or disable tracing."""
    tracer = get_tracer()
    tracer.enabled = enabled
    return {"success": True, "enabled": enabled}
