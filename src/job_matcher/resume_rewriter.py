"""
ResumeRewriter - Section-by-section resume rewriting with hallucination prevention.

Uses the AI provider with strict fact preservation constraints.
Each section is rewritten independently with explicit grounding rules.
"""

import logging
from typing import Optional, List, Dict, Any

from src.ai import get_ai_provider, AIProvider
from src.job_matcher.resume_parser import (
    ParsedResume, ExperienceEntry, ValidationRetryEngine
)
from src.job_matcher.models.resume_rewrite import (
    RewrittenResume, RewrittenSummary, RewrittenExperienceEntry,
    RewrittenSkills
)

logger = logging.getLogger(__name__)


class ResumeRewriter:
    """
    Rewrites resume sections for specific job applications.

    Key Design Principles:
    1. NEVER fabricate information - only use facts from original resume
    2. Preserve ALL factual content (dates, titles, companies, metrics)
    3. Only modify language/phrasing, not underlying facts
    4. Track all changes for verification
    """

    # System context emphasizing fact preservation
    SYSTEM_CONTEXT = """You are a professional resume writer. Your task is to rewrite resume sections to better match a job description.

CRITICAL RULES - YOU MUST FOLLOW THESE EXACTLY:
1. NEVER FABRICATE: Only use information from the original resume. Do not invent skills, achievements, or experiences.
2. PRESERVE ALL FACTS: Keep all dates, numbers, company names, job titles, and metrics EXACTLY as they appear.
3. REPHRASE ONLY: You may only change wording, not meaning. Incorporate keywords naturally.
4. NO ADDITIONS: Do not add accomplishments, skills, or experiences not in the original.
5. NO EXAGGERATION: Do not inflate numbers, scope, or impact beyond what's stated.

If you cannot improve a section while following these rules, return it unchanged."""

    def __init__(
        self,
        provider: Optional[AIProvider] = None,
        max_retries: int = 3,
        temperature: float = 0.3,
    ):
        """
        Initialize ResumeRewriter.

        Args:
            provider: Optional AIProvider instance. If not provided, uses get_ai_provider().
            max_retries: Maximum retry attempts on validation failure (default: 3)
            temperature: LLM temperature (default: 0.3 for consistency)
        """
        self.provider = provider or get_ai_provider()
        self.validation_engine = ValidationRetryEngine(
            provider=self.provider,
            max_retries=max_retries,
            temperature=temperature,
            max_tokens=4096,
        )
        self.temperature = temperature

    def rewrite_for_job(
        self,
        parsed_resume: ParsedResume,
        job: Dict[str, Any],
        gap_analysis: Optional[Dict[str, Any]] = None,
    ) -> Optional[RewrittenResume]:
        """
        Rewrite resume sections tailored for a specific job.

        Args:
            parsed_resume: Parsed resume from ResumeParser
            job: Job dict with title, company, description, requirements
            gap_analysis: Optional gap analysis from GapAnalyzer

        Returns:
            RewrittenResume with tracked changes, or None on failure
        """
        job_title = job.get("title", "Unknown Position")
        company = job.get("company", "Unknown Company")
        description = job.get("description", "")

        # Extract keywords from job
        keywords = self._extract_job_keywords(job, gap_analysis)

        logger.info(f"Rewriting resume for {job_title} at {company}")
        logger.info(f"Keywords to incorporate: {keywords[:10]}")

        # Rewrite each section independently
        rewritten_summary = self._rewrite_summary(
            parsed_resume.summary, job_title, company, description, keywords
        )

        rewritten_experience = self._rewrite_experience(
            parsed_resume.experience, job_title, description, keywords
        )

        rewritten_skills = self._rewrite_skills(
            parsed_resume.skills,
            job.get("skills", []),
            job.get("requirements", [])
        )

        if not rewritten_summary:
            logger.warning("Failed to rewrite summary, using original")
            rewritten_summary = RewrittenSummary(
                original=parsed_resume.summary,
                rewritten=parsed_resume.summary,
                keywords_added=[],
                changes_made=["No changes - rewrite failed"]
            )

        if not rewritten_experience:
            logger.error("Failed to rewrite experience")
            return None

        if not rewritten_skills:
            logger.warning("Failed to rewrite skills, using original")
            rewritten_skills = RewrittenSkills(
                original_skills=parsed_resume.skills,
                rewritten_skills=parsed_resume.skills,
                skills_highlighted=[],
                organization_strategy="Kept original order (rewrite failed)"
            )

        return RewrittenResume(
            contact=parsed_resume.contact,
            summary=rewritten_summary,
            experience=rewritten_experience,
            skills=rewritten_skills,
            education=parsed_resume.education,
            certifications=parsed_resume.certifications,
            languages=parsed_resume.languages,
            target_job_title=job_title,
            target_company=company,
            keywords_incorporated=keywords,
            overall_changes=self._compile_changes(
                rewritten_summary, rewritten_experience, rewritten_skills
            ),
        )

    def _extract_job_keywords(
        self,
        job: Dict[str, Any],
        gap_analysis: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Extract important keywords from job posting."""
        keywords = []

        # From job skills/requirements
        keywords.extend(job.get("skills", [])[:10])

        # From requirements list
        for req in job.get("requirements", [])[:5]:
            # Extract key terms from requirement strings
            if isinstance(req, str) and len(req) < 50:
                keywords.append(req)

        # From gap analysis recommendations
        if gap_analysis:
            keywords.extend(gap_analysis.get("keywords", [])[:5])

        # Deduplicate and limit
        seen = set()
        unique_keywords = []
        for kw in keywords:
            kw_lower = kw.lower() if isinstance(kw, str) else str(kw).lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                unique_keywords.append(kw)

        return unique_keywords[:15]

    def _rewrite_summary(
        self,
        original_summary: str,
        job_title: str,
        company: str,
        description: str,
        keywords: List[str],
    ) -> Optional[RewrittenSummary]:
        """Rewrite professional summary for job."""
        if not original_summary or not original_summary.strip():
            return RewrittenSummary(
                original="",
                rewritten="",
                keywords_added=[],
                changes_made=["No original summary to rewrite"]
            )

        prompt = f"""{self.SYSTEM_CONTEXT}

TASK: Rewrite this professional summary to better match the target job.

ORIGINAL SUMMARY:
{original_summary}

TARGET JOB:
Title: {job_title}
Company: {company}
Key Requirements: {', '.join(keywords[:8])}

INSTRUCTIONS:
1. Keep the same general structure and approximate length
2. Incorporate relevant keywords naturally (don't force them)
3. Emphasize aspects that match the job requirements
4. Preserve all factual claims from the original
5. Do NOT add new skills, achievements, or experiences

Return a JSON object with these exact fields:
- "original": the original summary text
- "rewritten": your rewritten summary
- "keywords_added": list of keywords you incorporated
- "changes_made": list describing what you changed and why"""

        result = self.validation_engine.extract(
            prompt=prompt,
            response_model=RewrittenSummary,
        )

        return result

    def _rewrite_experience(
        self,
        experience: List[ExperienceEntry],
        job_title: str,
        description: str,
        keywords: List[str],
    ) -> Optional[List[RewrittenExperienceEntry]]:
        """Rewrite experience bullets for job relevance."""
        rewritten_entries = []

        for entry in experience:
            rewritten_entry = self._rewrite_single_experience(
                entry, job_title, keywords
            )

            if rewritten_entry:
                # CRITICAL: Force-correct immutable fields
                if (rewritten_entry.title != entry.title or
                    rewritten_entry.company != entry.company or
                    rewritten_entry.start_date != entry.start_date or
                    rewritten_entry.end_date != entry.end_date):
                    logger.warning(f"LLM attempted to modify immutable fields for {entry.company}")
                    rewritten_entry.title = entry.title
                    rewritten_entry.company = entry.company
                    rewritten_entry.start_date = entry.start_date
                    rewritten_entry.end_date = entry.end_date
                    rewritten_entry.location = entry.location

                rewritten_entries.append(rewritten_entry)
            else:
                # On failure, use original unchanged
                rewritten_entries.append(RewrittenExperienceEntry(
                    title=entry.title,
                    company=entry.company,
                    start_date=entry.start_date,
                    end_date=entry.end_date,
                    location=entry.location,
                    original_bullets=entry.bullets,
                    rewritten_bullets=entry.bullets,
                    bullet_changes=["No changes - rewrite failed"],
                ))

        return rewritten_entries if rewritten_entries else None

    def _rewrite_single_experience(
        self,
        entry: ExperienceEntry,
        job_title: str,
        keywords: List[str],
    ) -> Optional[RewrittenExperienceEntry]:
        """Rewrite a single experience entry's bullets."""
        bullets_text = '\n'.join(f'- {b}' for b in entry.bullets)
        bullet_count = len(entry.bullets)

        prompt = f"""{self.SYSTEM_CONTEXT}

TASK: Rewrite the bullet points for this job experience to emphasize relevance to the target position.

ORIGINAL EXPERIENCE:
Title: {entry.title} (DO NOT CHANGE THIS)
Company: {entry.company} (DO NOT CHANGE THIS)
Dates: {entry.start_date} - {entry.end_date} (DO NOT CHANGE THESE)
Location: {entry.location} (DO NOT CHANGE THIS)

Original Bullets:
{bullets_text}

TARGET JOB KEYWORDS: {', '.join(keywords[:8])}

CRITICAL RULES FOR BULLETS:
1. Keep ALL numbers, metrics, and quantified achievements EXACTLY as stated
2. Keep exactly {bullet_count} bullets (same count as original)
3. Only rephrase to incorporate keywords - do not add new achievements
4. If a bullet cannot be improved, keep it unchanged
5. Preserve the meaning and facts of each bullet

Return a JSON object with these exact fields:
- "title": "{entry.title}"
- "company": "{entry.company}"
- "start_date": "{entry.start_date}"
- "end_date": "{entry.end_date}"
- "location": "{entry.location}"
- "original_bullets": the original bullets as a list
- "rewritten_bullets": your rewritten bullets as a list (exactly {bullet_count} items)
- "bullet_changes": list describing changes made to each bullet"""

        result = self.validation_engine.extract(
            prompt=prompt,
            response_model=RewrittenExperienceEntry,
        )

        return result

    def _rewrite_skills(
        self,
        original_skills: List[str],
        job_skills: List[str],
        job_requirements: List[str],
    ) -> Optional[RewrittenSkills]:
        """Reorganize skills section for relevance."""
        if not original_skills:
            return RewrittenSkills(
                original_skills=[],
                rewritten_skills=[],
                skills_highlighted=[],
                organization_strategy="No skills to reorder"
            )

        prompt = f"""{self.SYSTEM_CONTEXT}

TASK: Reorganize this skills section to emphasize the most relevant skills for the target job.

ORIGINAL SKILLS (total {len(original_skills)}):
{', '.join(original_skills)}

JOB REQUIRES THESE SKILLS:
{', '.join(job_skills[:10]) if job_skills else 'Not specified'}

INSTRUCTIONS:
1. Reorder skills to put most relevant ones first
2. Group related skills together if helpful
3. DO NOT add any skills not in the original list
4. DO NOT remove any skills from the original list
5. The output must contain exactly {len(original_skills)} skills

Return a JSON object with these exact fields:
- "original_skills": the original skills list
- "rewritten_skills": the reordered skills list (exactly {len(original_skills)} items)
- "skills_highlighted": which skills are most relevant to this job
- "organization_strategy": brief description of how you organized them"""

        result = self.validation_engine.extract(
            prompt=prompt,
            response_model=RewrittenSkills,
        )

        if result:
            # Validate no skills were added or removed
            original_set = set(s.lower().strip() for s in original_skills)
            rewritten_set = set(s.lower().strip() for s in result.rewritten_skills)

            if original_set != rewritten_set:
                logger.warning("LLM modified skills list - reverting to original order")
                result.rewritten_skills = original_skills
                result.organization_strategy = "Kept original order (validation failed - skill mismatch)"

            # Also check count
            if len(result.rewritten_skills) != len(original_skills):
                logger.warning(f"Skill count mismatch: {len(result.rewritten_skills)} vs {len(original_skills)}")
                result.rewritten_skills = original_skills
                result.organization_strategy = "Kept original order (validation failed - count mismatch)"

        return result

    def _compile_changes(
        self,
        summary: RewrittenSummary,
        experience: List[RewrittenExperienceEntry],
        skills: RewrittenSkills,
    ) -> List[str]:
        """Compile list of all changes made."""
        changes = []

        if summary.changes_made:
            changes.append(f"Summary: {len(summary.changes_made)} modification(s)")
            for change in summary.changes_made[:3]:
                changes.append(f"  - {change[:100]}")

        bullet_changes_count = 0
        for exp in experience:
            if exp.bullet_changes and exp.bullet_changes[0] != "No changes - rewrite failed":
                bullet_changes_count += len(exp.bullet_changes)
                changes.append(f"Experience ({exp.company}): {len(exp.bullet_changes)} bullet change(s)")

        if skills.organization_strategy and "failed" not in skills.organization_strategy.lower():
            changes.append(f"Skills: {skills.organization_strategy}")

        if not changes:
            changes.append("No significant changes made")

        return changes

    def test_connection(self) -> bool:
        """Test if the AI provider is available."""
        try:
            result = self.provider.test_connection()
            return result.success
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


def get_resume_rewriter(
    max_retries: int = 3,
    temperature: float = 0.3,
) -> ResumeRewriter:
    """
    Get a ResumeRewriter instance.

    Args:
        max_retries: Maximum retry attempts on validation failure
        temperature: LLM temperature (lower = more consistent)

    Returns:
        Configured ResumeRewriter instance
    """
    return ResumeRewriter(max_retries=max_retries, temperature=temperature)
