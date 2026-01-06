"""
Prompt Configuration System

Manages user-editable system prompts and LLM parameters for resume tailoring
and cover letter generation. Configurations are stored per-profile in YAML format.
"""

import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Models
# =============================================================================

class LLMParameters(BaseModel):
    """LLM parameters for a specific task."""
    temperature: float = Field(default=0.3, ge=0.0, le=2.0, description="Controls randomness (0=deterministic, 2=creative)")
    max_tokens: int = Field(default=4096, ge=256, le=16384, description="Maximum tokens in response")
    max_retries: int = Field(default=3, ge=1, le=10, description="Retry attempts on validation failure")


class ResumeRewriterConfig(BaseModel):
    """Configuration for resume rewriting."""
    system_prompt: str = Field(
        default="""You are a professional resume writer. Your task is to rewrite resume sections to better match a job description.

CRITICAL RULES - YOU MUST FOLLOW THESE EXACTLY:
1. NEVER FABRICATE: Only use information from the original resume. Do not invent skills, achievements, or experiences.
2. PRESERVE ALL FACTS: Keep all dates, numbers, company names, job titles, and metrics EXACTLY as they appear.
3. REPHRASE ONLY: You may only change wording, not meaning. Incorporate keywords naturally.
4. NO ADDITIONS: Do not add accomplishments, skills, or experiences not in the original.
5. NO EXAGGERATION: Do not inflate numbers, scope, or impact beyond what's stated.

If you cannot improve a section while following these rules, return it unchanged.""",
        description="System prompt for resume rewriting"
    )
    parameters: LLMParameters = Field(default_factory=lambda: LLMParameters(temperature=0.3))
    max_keywords: int = Field(default=10, ge=1, le=25, description="Maximum keywords to incorporate")

    # Section-specific instructions (appended to prompts)
    summary_instructions: str = Field(
        default="Focus on incorporating relevant keywords while maintaining the candidate's authentic voice and experience level.",
        description="Additional instructions for summary rewriting"
    )
    experience_instructions: str = Field(
        default="Enhance bullet points with action verbs and quantifiable results where already present. Do not add metrics that don't exist.",
        description="Additional instructions for experience bullet rewriting"
    )
    skills_instructions: str = Field(
        default="Reorder skills to prioritize those most relevant to the job. Do not add or remove skills.",
        description="Additional instructions for skills reordering"
    )


class CoverLetterConfig(BaseModel):
    """Configuration for cover letter generation."""
    system_prompt: str = Field(
        default="""You are a professional cover letter writer. Your task is to write a compelling cover letter.

CRITICAL ANTI-HALLUCINATION RULES:
1. ONLY use facts explicitly stated in the resume provided
2. DO NOT invent achievements, skills, experiences, or qualifications
3. DO NOT assume anything not explicitly stated in the resume
4. DO NOT add specific numbers, metrics, or details not in the resume
5. If the resume lacks information for a point, skip that point entirely
6. Every claim in the cover letter must be directly traceable to the resume

You will be given:
- The candidate's resume with all their actual experience
- The job description they're applying for
- Strengths analysis (if available)

Write a professional cover letter that highlights the candidate's ACTUAL qualifications.""",
        description="System prompt for cover letter generation"
    )
    parameters: LLMParameters = Field(default_factory=lambda: LLMParameters(temperature=0.5))

    # Tone options
    default_tone: str = Field(default="professional", description="Default tone: professional, enthusiastic, or formal")
    default_max_words: int = Field(default=400, ge=200, le=800, description="Default word count target")

    # Structure instructions
    opening_instructions: str = Field(
        default="Start with a compelling hook that connects your experience to the role. Mention the specific position and company.",
        description="Instructions for the opening paragraph"
    )
    body_instructions: str = Field(
        default="Highlight 2-3 key achievements from your resume that directly address job requirements. Use specific examples.",
        description="Instructions for body paragraphs"
    )
    closing_instructions: str = Field(
        default="Express enthusiasm for the opportunity and include a clear call to action.",
        description="Instructions for the closing paragraph"
    )


class VerificationConfig(BaseModel):
    """Configuration for information verification."""
    enabled: bool = Field(default=True, description="Enable dual verification (schema + LLM)")
    llm_verification_prompt: str = Field(
        default="""Compare the original resume to the rewritten version. Check for:
1. Any fabricated information not in the original
2. Changed dates, numbers, or metrics
3. Modified job titles or company names
4. Added skills or experiences
5. Exaggerated claims

Return PASSED only if all facts are preserved exactly.""",
        description="Prompt for LLM verification pass"
    )
    parameters: LLMParameters = Field(default_factory=lambda: LLMParameters(temperature=0.1))


# =============================================================================
# Job Matching Pipeline Configuration Models
# =============================================================================

class MatchScorerConfig(BaseModel):
    """Configuration for job scoring (Pass 1 of matching pipeline)."""
    system_prompt: str = Field(
        default="""You are an expert job matching system. Evaluate how well this job posting matches what the candidate is looking for AND whether they're qualified.

Complete each evaluation step and track your assessment. Your final score MUST reflect the cumulative result of all steps.

**STEP 1: DEAL-BREAKER CHECK**
Review ONLY the MUST-HAVES and AVOID lists (these are the ONLY deal-breakers):
- Does this job satisfy ALL MUST-HAVES? (Yes/No)
- Does this job contain ANY AVOID items? (Yes/No)
- If ANY deal-breaker is triggered → Cap score at 49 maximum

IMPORTANT: Skills and other preferences are NOT deal-breakers. A job missing some preferred skills should NOT be disqualified.

**STEP 2: DOMAIN MATCH CHECK**
Read the ENTIRE job description to determine the actual role:
- What is the primary domain? (e.g., data engineering, frontend, DevOps, etc.)
- Does this match the candidate's target domain? (Yes/Partial/No)
- If NO (wrong domain entirely) → Cap score at 59 maximum
- If PARTIAL (adjacent/overlapping domain) → Cap score at 74 maximum

**STEP 3: ROLE ALIGNMENT SCORING** (0-30 points)
How well does the role match what the candidate wants?
- 25-30: Exact target role match
- 18-24: Strong alignment
- 10-17: Moderate alignment
- 0-9: Weak alignment

**STEP 4: QUALIFICATIONS FIT SCORING** (0-40 points)
How qualified is the candidate for this specific role?
- 35-40: Exceeds requirements
- 28-34: Fully qualified
- 20-27: Mostly qualified
- 12-19: Partially qualified
- 0-11: Under-qualified

**STEP 5: PREFERENCES SCORING** (0-30 points)
How well does the job meet the candidate's stated preferences?
- Remote/location preference met? (0-10 points)
- Salary in acceptable range? (0-10 points)
- Other preferences? (0-10 points)

**SCORE INTERPRETATION:**
- 85-100: Strong match - Right role, qualified, core preferences met
- 70-84: Good match - Right domain, qualified, some trade-offs
- 50-69: Moderate match - Alignment concerns or significant gaps
- 0-49: Poor match - Wrong domain or deal-breaker triggered""",
        description="System prompt for job scoring evaluation"
    )
    parameters: LLMParameters = Field(default_factory=lambda: LLMParameters(temperature=0.2, max_tokens=2048))


class GapAnalyzerConfig(BaseModel):
    """Configuration for gap analysis (Pass 2 of matching pipeline)."""
    system_prompt: str = Field(
        default="""You are an expert career advisor providing detailed gap analysis to help candidates understand their fit for positions.

**ANALYSIS INSTRUCTIONS:**

1. **Strengths**: List 3-5 specific reasons why this candidate is a good fit. For each strength:
   - Reference actual experience from their resume
   - Connect it to specific job requirements
   - Focus on title match, skills alignment, experience level fit

2. **Gaps**: List specific skills, experience, or qualifications the candidate lacks. Organize by:
   - Title/Seniority gaps (e.g., "Job requires director-level, candidate is senior")
   - Skills gaps (specific technical skills they lack)
   - Experience gaps (years, certifications, etc.)
   - Compensation concerns (if salary below requirements)

3. **Red Flags**: Identify serious mismatches by checking:
   - MUST-HAVES violations (remote requirement, salary minimum, job type)
   - AVOID list items (contract work, wrong seniority, etc.)
   - Fundamental deal-breakers
   Leave empty if none.

4. **Overall Assessment**: Write 2-3 sentences summarizing:
   - Whether you'd recommend applying
   - How well each major section aligns
   - Whether this advances their career goals

Be specific and reference actual details from the resume and job description.""",
        description="System prompt for gap analysis"
    )
    parameters: LLMParameters = Field(default_factory=lambda: LLMParameters(temperature=0.4, max_tokens=2048))


class ResumeOptimizerConfig(BaseModel):
    """Configuration for resume optimization (Pass 3 of matching pipeline)."""
    system_prompt: str = Field(
        default="""You are an expert resume writer and career coach. Using the candidate's profile and resume, provide specific, actionable recommendations to tailor their resume for this job application.

**RECOMMENDATION CATEGORIES:**

1. **Keywords**: List 5-10 important keywords from the job description that should appear in the resume. Focus on technical skills, tools, and methodologies mentioned in the job posting.

2. **Experience Highlights**: List 3-5 specific bullets or achievements from the candidate's resume that should be FEATURED PROMINENTLY. Include the actual text from their resume.

3. **Sections to Expand**: List 2-3 sections of the resume that should be expanded or emphasized, with specific guidance on what to add.

4. **Cover Letter Points**: List 3-4 key talking points for the cover letter that directly address the job requirements and highlight relevant experience.

5. **Resume Summary**: Write a 2-3 sentence professional summary statement tailored specifically for this job application.

Be specific and actionable. Reference actual content from the resume where possible.""",
        description="System prompt for resume optimization recommendations"
    )
    parameters: LLMParameters = Field(default_factory=lambda: LLMParameters(temperature=0.5, max_tokens=2048))


class PromptConfig(BaseModel):
    """Complete prompt configuration for a profile."""
    version: str = Field(default="1.1", description="Config version for migrations")
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp")

    # Document generation prompts
    resume_rewriter: ResumeRewriterConfig = Field(default_factory=ResumeRewriterConfig)
    cover_letter: CoverLetterConfig = Field(default_factory=CoverLetterConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)

    # Job matching pipeline prompts
    match_scorer: MatchScorerConfig = Field(default_factory=MatchScorerConfig)
    gap_analyzer: GapAnalyzerConfig = Field(default_factory=GapAnalyzerConfig)
    resume_optimizer: ResumeOptimizerConfig = Field(default_factory=ResumeOptimizerConfig)


# =============================================================================
# Configuration Manager
# =============================================================================

class PromptConfigManager:
    """Manages loading and saving prompt configurations."""

    DEFAULT_CONFIG_FILENAME = "prompt_config.yaml"

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the config manager.

        Args:
            config_path: Path to config file. If None, uses active profile's templates dir.
        """
        if config_path is None:
            from src.utils.profile_manager import ProfilePaths
            paths = ProfilePaths()
            config_path = paths.templates_dir / self.DEFAULT_CONFIG_FILENAME

        self.config_path = Path(config_path)
        self._config: Optional[PromptConfig] = None

    def load(self, create_if_missing: bool = True) -> PromptConfig:
        """
        Load configuration from file.

        Args:
            create_if_missing: If True, creates default config if file doesn't exist

        Returns:
            PromptConfig instance
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                self._config = PromptConfig(**data)
                logger.info(f"Loaded prompt config from {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to load prompt config: {e}. Using defaults.")
                self._config = PromptConfig()
        else:
            self._config = PromptConfig()
            if create_if_missing:
                self.save()
                logger.info(f"Created default prompt config at {self.config_path}")

        return self._config

    def save(self, config: Optional[PromptConfig] = None) -> bool:
        """
        Save configuration to file.

        Args:
            config: Config to save. If None, saves current config.

        Returns:
            True if saved successfully
        """
        if config is not None:
            self._config = config

        if self._config is None:
            self._config = PromptConfig()

        # Update timestamp
        self._config.updated_at = datetime.now().isoformat()

        try:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert to dict and save as YAML
            data = self._config.model_dump()
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)

            logger.info(f"Saved prompt config to {self.config_path}")
            return True
        except Exception as e:
            logger.exception(f"Failed to save prompt config: {e}")
            return False

    def get_config(self) -> PromptConfig:
        """Get current config, loading if necessary."""
        if self._config is None:
            return self.load()
        return self._config

    def update_section(self, section: str, updates: Dict[str, Any]) -> PromptConfig:
        """
        Update a specific section of the config.

        Args:
            section: Section name ('resume_rewriter', 'cover_letter', 'verification')
            updates: Dictionary of updates to apply

        Returns:
            Updated PromptConfig
        """
        config = self.get_config()

        if hasattr(config, section):
            section_config = getattr(config, section)
            for key, value in updates.items():
                if hasattr(section_config, key):
                    if key == 'parameters' and isinstance(value, dict):
                        # Handle nested parameters
                        params = getattr(section_config, 'parameters')
                        for pk, pv in value.items():
                            if hasattr(params, pk):
                                setattr(params, pk, pv)
                    else:
                        setattr(section_config, key, value)

        self.save()
        return config

    def reset_to_defaults(self) -> PromptConfig:
        """Reset configuration to defaults."""
        self._config = PromptConfig()
        self.save()
        return self._config


# =============================================================================
# Convenience Functions
# =============================================================================

def get_prompt_config() -> PromptConfig:
    """Get the prompt config for the active profile."""
    manager = PromptConfigManager()
    return manager.load()


def get_resume_rewriter_config() -> ResumeRewriterConfig:
    """Get resume rewriter config for the active profile."""
    return get_prompt_config().resume_rewriter


def get_cover_letter_config() -> CoverLetterConfig:
    """Get cover letter config for the active profile."""
    return get_prompt_config().cover_letter


def get_match_scorer_config() -> MatchScorerConfig:
    """Get match scorer config for the active profile."""
    return get_prompt_config().match_scorer


def get_gap_analyzer_config() -> GapAnalyzerConfig:
    """Get gap analyzer config for the active profile."""
    return get_prompt_config().gap_analyzer


def get_resume_optimizer_config() -> ResumeOptimizerConfig:
    """Get resume optimizer config for the active profile."""
    return get_prompt_config().resume_optimizer
