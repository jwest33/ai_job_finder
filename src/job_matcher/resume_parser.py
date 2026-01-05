"""
Resume Parser - Robust LLM-based resume parsing with Pydantic validation

Uses the AI provider with Instructor-style validation and automatic retry logic.
Extracts structured data from plain text resumes with guaranteed schema compliance.
"""

import logging
import time
from typing import Optional, List, Type, TypeVar, Dict, Any
from pydantic import BaseModel, Field, ValidationError

from src.ai import get_ai_provider, AIProvider
from src.job_matcher.llm_tracer import get_tracer

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ============================================================================
# Pydantic Models - Define the exact structure we want from the LLM
# ============================================================================

class ContactInfo(BaseModel):
    """Contact information extracted from resume"""
    name: str = Field(default="", description="Full name of the candidate")
    email: str = Field(default="", description="Email address")
    phone: str = Field(default="", description="Phone number")
    location: str = Field(default="", description="City, State or full address")
    linkedin: str = Field(default="", description="LinkedIn URL or profile")
    website: str = Field(default="", description="Personal website or portfolio URL")


class ExperienceEntry(BaseModel):
    """A single work experience entry"""
    title: str = Field(default="", description="Job title")
    company: str = Field(default="", description="Company name")
    start_date: str = Field(default="", description="Start date (e.g., 'Jan 2020' or '2020')")
    end_date: str = Field(default="", description="End date or 'Present'")
    location: str = Field(default="", description="Job location")
    bullets: List[str] = Field(default_factory=list, description="List of accomplishments/responsibilities")


class EducationEntry(BaseModel):
    """A single education entry"""
    degree: str = Field(default="", description="Degree name (e.g., 'B.S. Computer Science')")
    school: str = Field(default="", description="School/University name")
    year: str = Field(default="", description="Graduation year or date range")
    gpa: str = Field(default="", description="GPA if mentioned")
    honors: str = Field(default="", description="Honors, awards, or distinctions")


class ParsedResume(BaseModel):
    """Complete parsed resume structure"""
    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str = Field(default="", description="Professional summary or objective")
    experience: List[ExperienceEntry] = Field(default_factory=list, description="Work experience entries")
    education: List[EducationEntry] = Field(default_factory=list, description="Education entries")
    skills: List[str] = Field(default_factory=list, description="List of skills")
    certifications: List[str] = Field(default_factory=list, description="Certifications and licenses")
    languages: List[str] = Field(default_factory=list, description="Languages spoken")


# ============================================================================
# Schema Description Generator
# ============================================================================

def generate_schema_description(model: Type[BaseModel], indent: int = 0) -> str:
    """
    Generate a human-readable schema description for the LLM.

    This is key to robust extraction - the LLM needs to understand
    the expected output format explicitly since the JSON schema
    constraint only affects token generation, not understanding.
    """
    lines = []
    prefix = "  " * indent

    schema = model.model_json_schema()
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    for field_name, field_info in properties.items():
        field_type = field_info.get("type", "any")
        description = field_info.get("description", "")
        is_required = field_name in required

        # Handle nested objects
        if field_type == "object" and "$ref" in field_info:
            ref_name = field_info["$ref"].split("/")[-1]
            lines.append(f"{prefix}- {field_name}: (object) {description}")
        elif field_type == "array":
            items = field_info.get("items", {})
            item_type = items.get("type", "any")
            if "$ref" in items:
                lines.append(f"{prefix}- {field_name}: (array of objects) {description}")
            else:
                lines.append(f"{prefix}- {field_name}: (array of {item_type}) {description}")
        else:
            req_marker = "*" if is_required else ""
            lines.append(f"{prefix}- {field_name}{req_marker}: ({field_type}) {description}")

    return "\n".join(lines)


# ============================================================================
# Instructor-Style Validation Engine
# ============================================================================

class ValidationRetryEngine:
    """
    Implements Instructor-style validation with automatic retry.

    When the LLM output fails Pydantic validation, this engine:
    1. Captures the validation errors
    2. Constructs a retry prompt with error feedback
    3. Retries until success or max_retries reached
    """

    def __init__(
        self,
        provider: AIProvider,
        max_retries: int = 3,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ):
        self.provider = provider
        self.max_retries = max_retries
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tracer = get_tracer()

    def extract(
        self,
        prompt: str,
        response_model: Type[T],
        context: Optional[str] = None,
        operation: Optional[str] = None,
        job_title: Optional[str] = None,
        job_company: Optional[str] = None,
    ) -> Optional[T]:
        """
        Extract structured data from LLM with validation and retry.

        Args:
            prompt: The extraction prompt
            response_model: Pydantic model class for validation
            context: Optional context to include in retry prompts
            operation: Operation name for tracing (e.g., "rewrite_summary")
            job_title: Job title for tracing context
            job_company: Company name for tracing context

        Returns:
            Validated Pydantic model instance or None if all retries fail
        """
        json_schema = response_model.model_json_schema()
        last_error: Optional[str] = None
        last_response: Optional[Dict[str, Any]] = None

        # Extract system prompt from the prompt if present (first section before newlines)
        system_prompt = ""
        user_prompt = prompt
        if "\n\n" in prompt:
            parts = prompt.split("\n\n", 1)
            if len(parts) == 2:
                system_prompt = parts[0]
                user_prompt = parts[1]

        # Start trace
        trace_id = self.tracer.start_trace(
            operation=operation or response_model.__name__,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=getattr(self.provider, 'model', 'unknown'),
            temperature=self.temperature,
            job_title=job_title,
            job_company=job_company,
            metadata={"response_model": response_model.__name__},
        )

        start_time = time.time()

        for attempt in range(self.max_retries + 1):
            # Build prompt with error feedback for retries
            current_prompt = prompt
            if attempt > 0 and last_error:
                current_prompt = self._build_retry_prompt(
                    original_prompt=prompt,
                    last_response=last_response,
                    validation_error=last_error,
                    attempt=attempt,
                )
                logger.info(f"Retry {attempt}/{self.max_retries} after validation error")
                self.tracer.record_retry(trace_id, last_error)

            # Generate JSON response
            result = self.provider.generate_json(
                prompt=current_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                json_schema=json_schema,
            )

            if result is None:
                logger.warning(f"Attempt {attempt + 1}: LLM returned no result")
                last_error = "LLM returned empty or unparseable response"
                continue

            last_response = result

            # Validate with Pydantic
            try:
                validated = response_model.model_validate(result)
                duration_ms = (time.time() - start_time) * 1000

                # Complete trace successfully
                self.tracer.complete_trace(
                    trace_id=trace_id,
                    response=str(result)[:2000],  # Truncate for storage
                    parsed_response=result,
                    duration_ms=duration_ms,
                    validation_passed=True,
                )

                if attempt > 0:
                    logger.info(f"Validation succeeded on retry {attempt}")
                return validated
            except ValidationError as e:
                last_error = self._format_validation_error(e)
                logger.debug(f"Attempt {attempt + 1} validation failed: {last_error}")
                continue

        # All attempts failed
        duration_ms = (time.time() - start_time) * 1000
        self.tracer.complete_trace(
            trace_id=trace_id,
            response=str(last_response)[:2000] if last_response else None,
            parsed_response=last_response,
            duration_ms=duration_ms,
            validation_passed=False,
            validation_errors=[last_error] if last_error else [],
        )

        logger.error(f"All {self.max_retries + 1} attempts failed. Last error: {last_error}")
        return None

    def _build_retry_prompt(
        self,
        original_prompt: str,
        last_response: Optional[Dict[str, Any]],
        validation_error: str,
        attempt: int,
    ) -> str:
        """Build a retry prompt with validation error feedback."""
        retry_section = f"""
---
VALIDATION ERROR (Attempt {attempt + 1}):
Your previous response had validation errors:
{validation_error}

Please fix these issues and try again. Ensure your response matches the required schema exactly.
---

{original_prompt}"""
        return retry_section

    def _format_validation_error(self, error: ValidationError) -> str:
        """Format Pydantic validation error for LLM feedback."""
        lines = []
        for err in error.errors():
            loc = " -> ".join(str(x) for x in err["loc"])
            msg = err["msg"]
            lines.append(f"  - Field '{loc}': {msg}")
        return "\n".join(lines)


# ============================================================================
# Resume Parser Class
# ============================================================================

class ResumeParser:
    """
    Parses resume text into structured data using LLM with Pydantic validation.

    Features:
    - Uses existing AI provider from src.ai module
    - Instructor-style automatic retry on validation failure
    - Explicit schema description in prompts for better extraction
    - Robust JSON extraction from various response formats
    """

    SYSTEM_CONTEXT = """You are an expert resume parser. Your task is to extract structured information from resume text.

IMPORTANT RULES:
1. Extract ALL information present in the resume - do not skip any sections
2. For fields not present in the resume, use empty string "" or empty array []
3. Preserve original wording from the resume for bullet points and descriptions
4. Dates should be in their original format (e.g., "Jan 2020", "2020", "January 2020 - Present")
5. Return ONLY valid JSON matching the schema - no explanations or additional text"""

    EXTRACTION_PROMPT = """Extract structured information from the following resume.

EXPECTED OUTPUT SCHEMA:
{schema_description}

RESUME TEXT:
---
{resume_text}
---

Extract all available information into the JSON structure. For any missing fields, use empty string or empty array as appropriate."""

    def __init__(
        self,
        provider: Optional[AIProvider] = None,
        max_retries: int = 3,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ):
        """
        Initialize Resume Parser.

        Args:
            provider: Optional AIProvider instance. If not provided, uses get_ai_provider().
            max_retries: Maximum retry attempts on validation failure (default: 3)
            temperature: LLM temperature for extraction (default: 0.1 for consistency)
            max_tokens: Maximum tokens for response (default: 4096)
        """
        self.provider = provider or get_ai_provider()
        self.validation_engine = ValidationRetryEngine(
            provider=self.provider,
            max_retries=max_retries,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Pre-generate schema description
        self._schema_description = self._generate_full_schema_description()

    def _generate_full_schema_description(self) -> str:
        """Generate complete schema description for prompts."""
        lines = [
            "Root object (ParsedResume):",
            "- contact: (object) Contact information",
            "    - name: (string) Full name",
            "    - email: (string) Email address",
            "    - phone: (string) Phone number",
            "    - location: (string) City, State or address",
            "    - linkedin: (string) LinkedIn URL",
            "    - website: (string) Personal website URL",
            "- summary: (string) Professional summary or objective statement",
            "- experience: (array) List of work experience entries, each with:",
            "    - title: (string) Job title",
            "    - company: (string) Company name",
            "    - start_date: (string) Start date",
            "    - end_date: (string) End date or 'Present'",
            "    - location: (string) Job location",
            "    - bullets: (array of strings) List of accomplishments/responsibilities",
            "- education: (array) List of education entries, each with:",
            "    - degree: (string) Degree name",
            "    - school: (string) School/University name",
            "    - year: (string) Graduation year or date range",
            "    - gpa: (string) GPA if mentioned",
            "    - honors: (string) Honors or distinctions",
            "- skills: (array of strings) Technical and soft skills",
            "- certifications: (array of strings) Certifications and licenses",
            "- languages: (array of strings) Languages spoken",
        ]
        return "\n".join(lines)

    def parse(self, resume_text: str) -> Optional[ParsedResume]:
        """
        Parse resume text into structured data.

        Args:
            resume_text: Plain text resume content

        Returns:
            ParsedResume object with extracted data, or None if parsing fails
        """
        if not resume_text or not resume_text.strip():
            logger.warning("Empty resume text provided")
            return None

        # Build extraction prompt with schema description
        prompt = f"{self.SYSTEM_CONTEXT}\n\n{self.EXTRACTION_PROMPT.format(schema_description=self._schema_description, resume_text=resume_text)}"

        # Use validation engine for extraction with retry
        result = self.validation_engine.extract(
            prompt=prompt,
            response_model=ParsedResume,
            context=resume_text[:500],  # First 500 chars as context for retries
        )

        return result

    def test_connection(self) -> bool:
        """Test if the AI provider is available."""
        try:
            result = self.provider.test_connection()
            return result.success
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


def get_resume_parser(
    max_retries: int = 3,
    temperature: float = 0.1,
) -> ResumeParser:
    """
    Get a ResumeParser instance.

    Args:
        max_retries: Maximum retry attempts on validation failure
        temperature: LLM temperature (lower = more consistent)

    Returns:
        Configured ResumeParser instance
    """
    return ResumeParser(max_retries=max_retries, temperature=temperature)


# ============================================================================
# Serialization helpers
# ============================================================================

def serialize_resume_to_text(data: ParsedResume) -> str:
    """
    Convert ParsedResume back to plain text format.

    Args:
        data: ParsedResume object

    Returns:
        Plain text resume
    """
    lines: List[str] = []

    # Contact info
    if data.contact.name:
        lines.append(data.contact.name)

    contact_line = " | ".join(filter(None, [
        data.contact.email,
        data.contact.phone,
        data.contact.location
    ]))
    if contact_line:
        lines.append(contact_line)

    if data.contact.linkedin:
        lines.append(data.contact.linkedin)
    if data.contact.website:
        lines.append(data.contact.website)

    lines.append("")

    # Summary
    if data.summary:
        lines.append(data.summary)
        lines.append("")

    # Experience
    if data.experience:
        lines.append("EXPERIENCE")
        lines.append("")

        for job in data.experience:
            title_line = " | ".join(filter(None, [job.title, job.company]))
            date_line = " - ".join(filter(None, [job.start_date, job.end_date]))
            if title_line:
                full_line = title_line
                if date_line:
                    full_line += f" | {date_line}"
                if job.location:
                    full_line += f" | {job.location}"
                lines.append(full_line)

            for bullet in job.bullets:
                if bullet.strip():
                    lines.append(f"  - {bullet}")

            lines.append("")

    # Education
    if data.education:
        lines.append("EDUCATION")
        lines.append("")

        for edu in data.education:
            edu_parts = [edu.degree, edu.school]
            if edu.year:
                edu_parts.append(edu.year)
            if edu.gpa:
                edu_parts.append(f"GPA: {edu.gpa}")
            lines.append(", ".join(filter(None, edu_parts)))
            if edu.honors:
                lines.append(f"  {edu.honors}")

        lines.append("")

    # Skills
    if data.skills:
        lines.append("SKILLS")
        lines.append("")
        lines.append(", ".join(data.skills))
        lines.append("")

    # Certifications
    if data.certifications:
        lines.append("CERTIFICATIONS")
        lines.append("")
        for cert in data.certifications:
            lines.append(f"  - {cert}")
        lines.append("")

    # Languages
    if data.languages:
        lines.append("LANGUAGES")
        lines.append("")
        lines.append(", ".join(data.languages))

    return "\n".join(lines).strip()


# ============================================================================
# CLI
# ============================================================================

def print_parsed_resume(result: ParsedResume, verbose: bool = False) -> None:
    """Print parsed resume in a readable format."""
    print(f"\nName: {result.contact.name}")
    print(f"Email: {result.contact.email}")
    print(f"Phone: {result.contact.phone}")
    print(f"Location: {result.contact.location}")
    if result.contact.linkedin:
        print(f"LinkedIn: {result.contact.linkedin}")
    if result.contact.website:
        print(f"Website: {result.contact.website}")

    if result.summary:
        summary_display = result.summary[:100] + "..." if len(result.summary) > 100 else result.summary
        print(f"\nSummary: {summary_display}")

    print(f"\nExperience: {len(result.experience)} entries")
    for job in result.experience:
        print(f"  - {job.title} at {job.company} ({job.start_date} - {job.end_date})")
        if verbose:
            for bullet in job.bullets:
                print(f"      * {bullet[:80]}{'...' if len(bullet) > 80 else ''}")

    print(f"\nEducation: {len(result.education)} entries")
    for edu in result.education:
        print(f"  - {edu.degree} from {edu.school}" + (f" ({edu.year})" if edu.year else ""))

    print(f"\nSkills: {len(result.skills)}")
    if result.skills:
        skills_display = ", ".join(result.skills[:8])
        if len(result.skills) > 8:
            skills_display += f"... (+{len(result.skills) - 8} more)"
        print(f"  {skills_display}")

    if result.certifications:
        print(f"\nCertifications: {len(result.certifications)}")
        for cert in result.certifications:
            print(f"  - {cert}")

    if result.languages:
        print(f"\nLanguages: {', '.join(result.languages)}")


if __name__ == "__main__":
    import sys
    import argparse

    arg_parser = argparse.ArgumentParser(
        description="Parse resume text into structured data using LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.job_matcher.resume_parser resume.txt
  python -m src.job_matcher.resume_parser profiles/default/templates/resume.txt -v
  python -m src.job_matcher.resume_parser --json resume.txt > parsed.json
  cat resume.txt | python -m src.job_matcher.resume_parser -
"""
    )
    arg_parser.add_argument(
        "file",
        nargs="?",
        help="Path to resume text file (use '-' for stdin, omit for sample)"
    )
    arg_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed output including bullet points"
    )
    arg_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of formatted text"
    )
    arg_parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Max retry attempts on validation failure (default: 3)"
    )

    args = arg_parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Load resume text
    if args.file == "-":
        # Read from stdin
        resume_text = sys.stdin.read()
    elif args.file:
        # Read from file
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                resume_text = f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Use sample resume
        resume_text = """
John Smith
john.smith@email.com | (555) 123-4567 | New York, NY
linkedin.com/in/johnsmith

Experienced software engineer with 5+ years building scalable web applications.

EXPERIENCE

Senior Software Engineer | Tech Corp | Jan 2022 - Present | San Francisco, CA
- Led development of microservices architecture serving 10M+ users
- Reduced API latency by 40% through database optimization
- Mentored team of 3 junior developers

Software Engineer | StartupXYZ | Jun 2019 - Dec 2021 | New York, NY
- Built real-time data pipeline processing 1M events/day
- Implemented CI/CD pipelines reducing deployment time by 60%

EDUCATION

B.S. Computer Science, MIT, 2019
GPA: 3.8, Magna Cum Laude

SKILLS

Python, JavaScript, TypeScript, React, Node.js, PostgreSQL, AWS, Docker, Kubernetes

CERTIFICATIONS

AWS Solutions Architect
Google Cloud Professional

LANGUAGES

English (Native), Spanish (Conversational)
"""
        if not args.json:
            print("Using sample resume (pass a file path to parse your own)")
            print("=" * 60)

    # Initialize parser
    parser = ResumeParser(max_retries=args.retries)

    if not parser.test_connection():
        print("Error: Cannot connect to AI provider. Is it running?", file=sys.stderr)
        sys.exit(1)

    # Parse
    if not args.json:
        print("Parsing resume...")

    result = parser.parse(resume_text)

    if result:
        if args.json:
            print(result.model_dump_json(indent=2))
        else:
            print("\n" + "=" * 60)
            print("PARSING SUCCESSFUL")
            print("=" * 60)
            print_parsed_resume(result, verbose=args.verbose)
    else:
        print("Error: Parsing failed after all retry attempts", file=sys.stderr)
        sys.exit(1)
