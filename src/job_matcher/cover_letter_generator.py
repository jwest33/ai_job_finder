"""
CoverLetterGenerator - Generate cover letters grounded in resume facts.

Generates complete cover letters using ONLY facts from the resume.
Implements strict grounding to prevent hallucination.
"""

import logging
from typing import Optional, List, Dict, Any

from src.ai import get_ai_provider, AIProvider
from src.job_matcher.resume_parser import ParsedResume, ValidationRetryEngine
from src.job_matcher.models.resume_rewrite import (
    CoverLetter, CoverLetterParagraph
)

logger = logging.getLogger(__name__)


class CoverLetterGenerator:
    """
    Generates cover letters grounded strictly in resume facts.

    Anti-hallucination Strategy:
    1. Explicit fact extraction from resume before generation
    2. Each paragraph must cite which resume facts it uses
    3. Post-generation verification that no new facts were added
    """

    SYSTEM_CONTEXT = """You are a professional cover letter writer. Your task is to write a compelling cover letter.

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

Write a professional cover letter that highlights the candidate's ACTUAL qualifications."""

    def __init__(
        self,
        provider: Optional[AIProvider] = None,
        max_retries: int = 3,
        temperature: float = 0.5,
    ):
        """
        Initialize CoverLetterGenerator.

        Args:
            provider: Optional AIProvider instance
            max_retries: Maximum retry attempts on validation failure
            temperature: LLM temperature (slightly higher for natural writing)
        """
        self.provider = provider or get_ai_provider()
        self.validation_engine = ValidationRetryEngine(
            provider=self.provider,
            max_retries=max_retries,
            temperature=temperature,
            max_tokens=4096,
        )

    def generate(
        self,
        parsed_resume: ParsedResume,
        job: Dict[str, Any],
        gap_analysis: Optional[Dict[str, Any]] = None,
        tone: str = "professional",
        max_words: int = 400,
        template: Optional[str] = None,
    ) -> Optional[CoverLetter]:
        """
        Generate a cover letter for a specific job.

        Args:
            parsed_resume: Parsed resume with structured data
            job: Job dict with title, company, description
            gap_analysis: Optional gap analysis with strengths/gaps
            tone: Writing tone (professional, enthusiastic, formal)
            max_words: Target word count
            template: Optional cover letter template to use as style reference

        Returns:
            CoverLetter with cited facts, or None on failure
        """
        # Step 1: Extract facts from resume for grounding
        resume_facts = self._extract_resume_facts(parsed_resume)

        job_title = job.get("title", "the position")
        company = job.get("company", "your company")
        description = job.get("description", "")

        logger.info(f"Generating cover letter for {job_title} at {company}")
        logger.info(f"Extracted {len(resume_facts)} facts from resume for grounding")

        # Step 2: Generate cover letter with fact grounding
        prompt = self._build_generation_prompt(
            parsed_resume=parsed_resume,
            resume_facts=resume_facts,
            job_title=job_title,
            company=company,
            description=description,
            gap_analysis=gap_analysis,
            tone=tone,
            max_words=max_words,
            template=template,
        )

        result = self.validation_engine.extract(
            prompt=prompt,
            response_model=CoverLetter,
        )

        if result:
            # Add metadata
            result.target_job_title = job_title
            result.target_company = company
            result.word_count = len(result.to_text().split())
            result.signature = parsed_resume.contact.name

            # Step 3: Verify no hallucinations
            grounding_check = self._verify_grounding(result, resume_facts)
            if not grounding_check:
                logger.warning("Cover letter may contain ungrounded claims - flagging for review")
                # Still return it, but the warning is logged

            logger.info(f"Generated cover letter: {result.word_count} words")

        return result

    def _extract_resume_facts(self, resume: ParsedResume) -> List[str]:
        """Extract all verifiable facts from resume for grounding."""
        facts = []

        # Contact facts
        if resume.contact.name:
            facts.append(f"Candidate name: {resume.contact.name}")

        # Summary facts
        if resume.summary:
            facts.append(f"Summary: {resume.summary[:200]}")

        # Experience facts
        for exp in resume.experience:
            facts.append(f"Worked as {exp.title} at {exp.company}")
            facts.append(f"Employment: {exp.start_date} to {exp.end_date}")
            if exp.location:
                facts.append(f"Location: {exp.location}")
            for bullet in exp.bullets:
                # Each bullet is a fact
                facts.append(f"Achievement: {bullet}")

        # Education facts
        for edu in resume.education:
            facts.append(f"Education: {edu.degree} from {edu.school}")
            if edu.year:
                facts.append(f"Graduated: {edu.year}")
            if edu.gpa:
                facts.append(f"GPA: {edu.gpa}")
            if edu.honors:
                facts.append(f"Honors: {edu.honors}")

        # Skills facts
        for skill in resume.skills:
            facts.append(f"Has skill: {skill}")

        # Certifications
        for cert in resume.certifications:
            facts.append(f"Certification: {cert}")

        # Languages
        for lang in resume.languages:
            facts.append(f"Language: {lang}")

        return facts

    def _build_generation_prompt(
        self,
        parsed_resume: ParsedResume,
        resume_facts: List[str],
        job_title: str,
        company: str,
        description: str,
        gap_analysis: Optional[Dict[str, Any]],
        tone: str,
        max_words: int,
        template: Optional[str] = None,
    ) -> str:
        """Build the cover letter generation prompt."""
        # Format resume as text
        resume_text = self._format_resume_for_prompt(parsed_resume)

        # Format strengths if available
        strengths_text = ""
        if gap_analysis and gap_analysis.get("strengths"):
            strengths = gap_analysis["strengths"]
            if isinstance(strengths, list):
                strengths_text = f"\n\nCANDIDATE STRENGTHS FOR THIS ROLE:\n" + "\n".join(f"- {s}" for s in strengths[:5])

        # Format template reference if provided
        template_text = ""
        if template:
            template_text = f"""

STYLE TEMPLATE (use this as a reference for structure and tone):
{template[:2000]}

IMPORTANT: Use the structure and style of this template, but replace ALL content with facts from the candidate's resume. Do NOT copy any specific claims from the template."""

        # Limit facts to show in prompt
        facts_to_show = resume_facts[:25]

        return f"""{self.SYSTEM_CONTEXT}

CANDIDATE'S RESUME:
{resume_text}

AVAILABLE FACTS FROM RESUME (you can ONLY use these facts):
{chr(10).join(f'- {fact}' for fact in facts_to_show)}

TARGET JOB:
Title: {job_title}
Company: {company}

Job Description:
{description[:2000]}
{strengths_text}
{template_text}

COVER LETTER REQUIREMENTS:
- Tone: {tone}
- Target length: approximately {max_words} words (3-4 paragraphs)
- Structure:
  1. Opening paragraph - express interest and summarize fit
  2. 1-2 body paragraphs - highlight relevant experience with SPECIFIC examples from resume
  3. Closing paragraph - express enthusiasm and call to action

CRITICAL INSTRUCTIONS:
- For each paragraph, you MUST list which specific facts from the resume you used
- Do NOT add any skills, achievements, numbers, or experiences not explicitly in the resume
- If you're unsure if something is in the resume, DO NOT include it

Return a JSON object with these exact fields:
- "greeting": the salutation (e.g., "Dear Hiring Manager,")
- "paragraphs": array of paragraph objects, each with:
  - "type": "opening", "body", or "closing"
  - "content": the paragraph text
  - "facts_used": list of facts from the resume used in this paragraph
- "closing": the sign-off phrase (e.g., "Sincerely,")
- "signature": "{parsed_resume.contact.name}"
- "facts_from_resume": complete list of all facts referenced
- "job_requirements_addressed": which job requirements you addressed"""

    def _format_resume_for_prompt(self, resume: ParsedResume) -> str:
        """Format resume for inclusion in prompt."""
        lines = []
        lines.append(f"Name: {resume.contact.name}")
        if resume.contact.email:
            lines.append(f"Email: {resume.contact.email}")
        if resume.contact.phone:
            lines.append(f"Phone: {resume.contact.phone}")
        if resume.contact.location:
            lines.append(f"Location: {resume.contact.location}")
        lines.append("")

        if resume.summary:
            lines.append(f"SUMMARY: {resume.summary}")
            lines.append("")

        lines.append("EXPERIENCE:")
        for exp in resume.experience:
            lines.append(f"  {exp.title} at {exp.company}")
            lines.append(f"  {exp.start_date} - {exp.end_date}")
            if exp.location:
                lines.append(f"  Location: {exp.location}")
            for bullet in exp.bullets[:6]:  # Limit bullets
                lines.append(f"    - {bullet}")
            lines.append("")

        if resume.skills:
            lines.append(f"SKILLS: {', '.join(resume.skills[:20])}")
            lines.append("")

        if resume.education:
            lines.append("EDUCATION:")
            for edu in resume.education:
                edu_line = f"  {edu.degree} - {edu.school}"
                if edu.year:
                    edu_line += f" ({edu.year})"
                lines.append(edu_line)
                if edu.gpa:
                    lines.append(f"    GPA: {edu.gpa}")
                if edu.honors:
                    lines.append(f"    {edu.honors}")
            lines.append("")

        if resume.certifications:
            lines.append(f"CERTIFICATIONS: {', '.join(resume.certifications)}")
            lines.append("")

        if resume.languages:
            lines.append(f"LANGUAGES: {', '.join(resume.languages)}")

        return "\n".join(lines)

    def _verify_grounding(
        self,
        cover_letter: CoverLetter,
        resume_facts: List[str]
    ) -> bool:
        """Verify cover letter is grounded in resume facts."""
        # Collect all cited facts from paragraphs
        all_cited_facts = []
        for para in cover_letter.paragraphs:
            all_cited_facts.extend(para.facts_used)

        if not all_cited_facts:
            logger.warning("No facts were cited in cover letter paragraphs")
            return False

        # Create lowercase versions for matching
        resume_facts_lower = [f.lower() for f in resume_facts]

        ungrounded_count = 0
        for cited in all_cited_facts:
            cited_lower = cited.lower()
            # Check if any resume fact contains key terms from cited fact
            cited_terms = set(cited_lower.split())

            found = False
            for rf in resume_facts_lower:
                rf_terms = set(rf.split())
                # If at least 2 significant terms overlap, consider it grounded
                overlap = cited_terms.intersection(rf_terms)
                significant_overlap = [t for t in overlap if len(t) > 3]
                if len(significant_overlap) >= 2:
                    found = True
                    break

            if not found:
                logger.debug(f"Potentially ungrounded fact: {cited[:100]}")
                ungrounded_count += 1

        # Allow some flexibility - flag if more than 30% ungrounded
        grounding_ratio = 1 - (ungrounded_count / len(all_cited_facts)) if all_cited_facts else 0
        logger.info(f"Grounding ratio: {grounding_ratio:.2%}")

        return grounding_ratio >= 0.7

    def test_connection(self) -> bool:
        """Test if the AI provider is available."""
        try:
            result = self.provider.test_connection()
            return result.success
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


def get_cover_letter_generator(
    max_retries: int = 3,
    temperature: float = 0.5,
) -> CoverLetterGenerator:
    """
    Get a CoverLetterGenerator instance.

    Args:
        max_retries: Maximum retry attempts
        temperature: LLM temperature

    Returns:
        Configured CoverLetterGenerator instance
    """
    return CoverLetterGenerator(max_retries=max_retries, temperature=temperature)
