"""
InformationVerifier - Dual verification for resume rewriting.

Implements two-pass verification:
1. Schema diff: Programmatic comparison of structured fields
2. LLM verification: AI-based fact checking for subtle issues
"""

import logging
from typing import Optional, List, Set

from src.ai import get_ai_provider, AIProvider
from src.job_matcher.resume_parser import ParsedResume, ValidationRetryEngine
from src.job_matcher.models.resume_rewrite import (
    RewrittenResume, VerificationReport, VerificationStatus,
    SchemaVerificationResult, LLMVerificationResult, FactDiscrepancy
)

logger = logging.getLogger(__name__)


class InformationVerifier:
    """
    Verifies that rewritten resume preserves all original information.

    Two-pass verification:
    1. Schema Diff: Fast programmatic comparison of structured fields
    2. LLM Verification: Deep semantic check for subtle information loss
    """

    LLM_VERIFICATION_PROMPT = """You are a fact-checking assistant. Your task is to verify that a rewritten resume preserves ALL factual information from the original.

ORIGINAL RESUME:
{original_text}

REWRITTEN RESUME:
{rewritten_text}

VERIFICATION CHECKLIST - Check each item carefully:
1. Are ALL job titles preserved exactly? (e.g., "Senior Engineer" not changed to "Lead Engineer")
2. Are ALL company names preserved exactly?
3. Are ALL dates (start/end) preserved exactly?
4. Are ALL numbers and metrics preserved exactly (percentages, dollar amounts, team sizes, user counts)?
5. Are ALL skills from the original present in the rewritten version?
6. Are ALL certifications and education entries preserved?
7. Has any FABRICATED information been added? Check for:
   - New job experiences or achievements not implied by the original
   - Made-up metrics, numbers, or quantified results
   - New certifications, degrees, or credentials
   - Claims about technologies or skills with NO basis in the original

WHAT IS ACCEPTABLE (do NOT flag these as issues):
- Rewording bullets for clarity while preserving meaning
- Adding industry keywords that describe existing work (e.g., "built pipelines" → "built ETL/ELT data pipelines")
- Emphasizing relevant aspects of existing experience
- Reorganizing or reordering skills
- Making implicit skills explicit (e.g., if they built dashboards, mentioning "data visualization")

WHAT IS NOT ACCEPTABLE (flag these):
- Inventing new achievements or metrics not in the original
- Adding certifications, degrees, or job experiences
- Claiming mastery of technologies not mentioned or implied
- Changing factual details (dates, company names, titles)

Return a JSON object with these exact fields:
- "passed": true if all facts are preserved (acceptable changes are OK), false only for fabrications
- "confidence": your confidence score from 0.0 to 1.0
- "findings": list of your observations about fact preservation
- "potential_issues": list of any fabricated facts (not just rewordings)
- "recommendation": either "APPROVE - facts preserved" or "REJECT - [specific fabrication found]" """

    def __init__(
        self,
        provider: Optional[AIProvider] = None,
        max_retries: int = 2,
    ):
        """
        Initialize InformationVerifier.

        Args:
            provider: Optional AIProvider instance
            max_retries: Maximum retry attempts for LLM verification
        """
        self.provider = provider or get_ai_provider()
        self.validation_engine = ValidationRetryEngine(
            provider=self.provider,
            max_retries=max_retries,
            temperature=0.1,  # Very low for consistency
            max_tokens=2048,
        )

    def verify(
        self,
        original: ParsedResume,
        rewritten: RewrittenResume,
    ) -> VerificationReport:
        """
        Perform dual verification on rewritten resume.

        Args:
            original: Original parsed resume
            rewritten: Rewritten resume to verify

        Returns:
            VerificationReport with both check results
        """
        logger.info("Starting dual verification (schema + LLM)")

        # Pass 1: Schema diff (fast, programmatic)
        schema_result = self._verify_schema(original, rewritten)
        logger.info(f"Schema check: {'PASSED' if schema_result.passed else 'FAILED'}")

        # Pass 2: LLM verification (deep, semantic)
        llm_result = self._verify_with_llm(original, rewritten)
        logger.info(f"LLM check: {'PASSED' if llm_result.passed else 'FAILED'} (confidence: {llm_result.confidence})")

        # Determine overall status
        overall_passed = schema_result.passed and llm_result.passed

        if overall_passed:
            status = VerificationStatus.PASSED
            summary = "All verification checks passed. Resume preserves original information."
        elif schema_result.passed and not llm_result.passed:
            status = VerificationStatus.WARNING
            summary = f"Schema check passed but LLM found potential issues: {llm_result.recommendation}"
        else:
            status = VerificationStatus.FAILED
            critical_count = len([d for d in schema_result.discrepancies if d.severity == "critical"])
            summary = f"Verification failed. Found {critical_count} critical discrepancies."

        return VerificationReport(
            status=status,
            schema_check=schema_result,
            llm_check=llm_result,
            overall_passed=overall_passed,
            summary=summary,
        )

    def _verify_schema(
        self,
        original: ParsedResume,
        rewritten: RewrittenResume,
    ) -> SchemaVerificationResult:
        """Programmatic schema comparison."""
        discrepancies = []
        checks = {}

        # Check 1: Contact info unchanged
        contact_match = (
            original.contact.name == rewritten.contact.name and
            original.contact.email == rewritten.contact.email and
            original.contact.phone == rewritten.contact.phone
        )
        checks["contact_unchanged"] = contact_match
        if not contact_match:
            discrepancies.append(FactDiscrepancy(
                section="contact",
                field="contact_info",
                original_value=f"{original.contact.name}, {original.contact.email}",
                rewritten_value=f"{rewritten.contact.name}, {rewritten.contact.email}",
                discrepancy_type="modified",
                severity="critical",
            ))

        # Check 2: All jobs present with correct metadata
        original_jobs = {(e.company, e.title) for e in original.experience}
        rewritten_jobs = {(e.company, e.title) for e in rewritten.experience}
        checks["all_jobs_present"] = original_jobs == rewritten_jobs

        if original_jobs != rewritten_jobs:
            missing = original_jobs - rewritten_jobs
            added = rewritten_jobs - original_jobs
            for company, title in missing:
                discrepancies.append(FactDiscrepancy(
                    section="experience",
                    field="job_entry",
                    original_value=f"{title} at {company}",
                    rewritten_value="MISSING",
                    discrepancy_type="missing",
                    severity="critical",
                ))
            for company, title in added:
                discrepancies.append(FactDiscrepancy(
                    section="experience",
                    field="job_entry",
                    original_value="NOT IN ORIGINAL",
                    rewritten_value=f"{title} at {company}",
                    discrepancy_type="fabricated",
                    severity="critical",
                ))

        # Check 3: Dates unchanged for each job
        dates_match = True
        for orig in original.experience:
            # Find corresponding rewritten entry
            for rewr in rewritten.experience:
                if rewr.company == orig.company and rewr.title == orig.title:
                    if orig.start_date != rewr.start_date or orig.end_date != rewr.end_date:
                        dates_match = False
                        discrepancies.append(FactDiscrepancy(
                            section="experience",
                            field=f"dates_{orig.company}",
                            original_value=f"{orig.start_date} - {orig.end_date}",
                            rewritten_value=f"{rewr.start_date} - {rewr.end_date}",
                            discrepancy_type="modified",
                            severity="critical",
                        ))
                    break
        checks["no_dates_changed"] = dates_match

        # Check 4: Job titles unchanged
        titles_match = True
        for orig in original.experience:
            found = False
            for rewr in rewritten.experience:
                if rewr.company == orig.company:
                    found = True
                    if rewr.title != orig.title:
                        titles_match = False
                        discrepancies.append(FactDiscrepancy(
                            section="experience",
                            field=f"title_{orig.company}",
                            original_value=orig.title,
                            rewritten_value=rewr.title,
                            discrepancy_type="modified",
                            severity="critical",
                        ))
                    break
            if not found:
                titles_match = False
        checks["no_titles_changed"] = titles_match

        # Check 5: Education unchanged
        education_match = len(original.education) == len(rewritten.education)
        if education_match:
            for orig_edu, rewr_edu in zip(original.education, rewritten.education):
                if (orig_edu.degree != rewr_edu.degree or
                    orig_edu.school != rewr_edu.school or
                    orig_edu.year != rewr_edu.year):
                    education_match = False
                    discrepancies.append(FactDiscrepancy(
                        section="education",
                        field="education_entry",
                        original_value=f"{orig_edu.degree} from {orig_edu.school}",
                        rewritten_value=f"{rewr_edu.degree} from {rewr_edu.school}",
                        discrepancy_type="modified",
                        severity="critical",
                    ))
        checks["all_education_present"] = education_match

        # Check 6: Skills count and content preserved
        original_skills = set(s.lower().strip() for s in original.skills)
        rewritten_skills = set(s.lower().strip() for s in rewritten.skills.rewritten_skills)

        missing_skills = original_skills - rewritten_skills
        added_skills = rewritten_skills - original_skills

        skills_match = len(missing_skills) == 0 and len(added_skills) == 0
        checks["skill_count_preserved"] = skills_match
        checks["no_skills_removed"] = len(missing_skills) == 0
        checks["no_skills_fabricated"] = len(added_skills) == 0

        if missing_skills:
            discrepancies.append(FactDiscrepancy(
                section="skills",
                field="skills_list",
                original_value=f"Missing: {', '.join(list(missing_skills)[:5])}",
                rewritten_value="Not present in rewritten",
                discrepancy_type="missing",
                severity="warning",
            ))

        if added_skills:
            discrepancies.append(FactDiscrepancy(
                section="skills",
                field="skills_list",
                original_value="Not in original",
                rewritten_value=f"Fabricated: {', '.join(list(added_skills)[:5])}",
                discrepancy_type="fabricated",
                severity="critical",
            ))

        # Check 7: Bullet counts match per experience
        for orig in original.experience:
            for rewr in rewritten.experience:
                if rewr.company == orig.company and rewr.title == orig.title:
                    if len(orig.bullets) != len(rewr.rewritten_bullets):
                        discrepancies.append(FactDiscrepancy(
                            section="experience",
                            field=f"bullet_count_{orig.company}",
                            original_value=str(len(orig.bullets)),
                            rewritten_value=str(len(rewr.rewritten_bullets)),
                            discrepancy_type="modified",
                            severity="warning",
                        ))
                    break

        # Determine overall pass/fail
        critical_discrepancies = [d for d in discrepancies if d.severity == "critical"]
        passed = all(checks.values()) and len(critical_discrepancies) == 0

        return SchemaVerificationResult(
            passed=passed,
            discrepancies=discrepancies,
            checks_performed=checks,
        )

    def _verify_with_llm(
        self,
        original: ParsedResume,
        rewritten: RewrittenResume,
    ) -> LLMVerificationResult:
        """LLM-based semantic verification."""
        # Serialize both resumes to text for comparison
        original_text = self._serialize_for_comparison(original)
        rewritten_text = self._serialize_rewritten_for_comparison(rewritten)

        prompt = self.LLM_VERIFICATION_PROMPT.format(
            original_text=original_text,
            rewritten_text=rewritten_text,
        )

        result = self.validation_engine.extract(
            prompt=prompt,
            response_model=LLMVerificationResult,
        )

        if not result:
            # On failure, return conservative result
            logger.warning("LLM verification failed to complete")
            return LLMVerificationResult(
                passed=False,
                confidence=0.0,
                findings=["LLM verification failed to complete"],
                potential_issues=["Unable to verify - manual review required"],
                recommendation="REJECT - verification incomplete",
            )

        return result

    def _serialize_for_comparison(self, resume: ParsedResume) -> str:
        """Serialize ParsedResume for LLM comparison."""
        lines = []
        lines.append(f"Name: {resume.contact.name}")
        lines.append(f"Email: {resume.contact.email}")
        lines.append(f"Phone: {resume.contact.phone}")
        lines.append("")

        if resume.summary:
            lines.append(f"Summary: {resume.summary}")
            lines.append("")

        lines.append("EXPERIENCE:")
        for exp in resume.experience:
            lines.append(f"  {exp.title} at {exp.company}")
            lines.append(f"  {exp.start_date} - {exp.end_date}, {exp.location}")
            for bullet in exp.bullets:
                lines.append(f"    - {bullet}")
            lines.append("")

        lines.append(f"SKILLS: {', '.join(resume.skills)}")
        lines.append("")

        lines.append("EDUCATION:")
        for edu in resume.education:
            lines.append(f"  {edu.degree} from {edu.school}, {edu.year}")

        if resume.certifications:
            lines.append("")
            lines.append(f"CERTIFICATIONS: {', '.join(resume.certifications)}")

        return "\n".join(lines)

    def _serialize_rewritten_for_comparison(self, resume: RewrittenResume) -> str:
        """Serialize RewrittenResume for LLM comparison."""
        lines = []
        lines.append(f"Name: {resume.contact.name}")
        lines.append(f"Email: {resume.contact.email}")
        lines.append(f"Phone: {resume.contact.phone}")
        lines.append("")

        if resume.summary.rewritten:
            lines.append(f"Summary: {resume.summary.rewritten}")
            lines.append("")

        lines.append("EXPERIENCE:")
        for exp in resume.experience:
            lines.append(f"  {exp.title} at {exp.company}")
            lines.append(f"  {exp.start_date} - {exp.end_date}, {exp.location}")
            for bullet in exp.rewritten_bullets:
                lines.append(f"    - {bullet}")
            lines.append("")

        lines.append(f"SKILLS: {', '.join(resume.skills.rewritten_skills)}")
        lines.append("")

        lines.append("EDUCATION:")
        for edu in resume.education:
            lines.append(f"  {edu.degree} from {edu.school}, {edu.year}")

        if resume.certifications:
            lines.append("")
            lines.append(f"CERTIFICATIONS: {', '.join(resume.certifications)}")

        return "\n".join(lines)

    def test_connection(self) -> bool:
        """Test if the AI provider is available."""
        try:
            result = self.provider.test_connection()
            return result.success
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


def get_information_verifier(max_retries: int = 2) -> InformationVerifier:
    """Get an InformationVerifier instance."""
    return InformationVerifier(max_retries=max_retries)
