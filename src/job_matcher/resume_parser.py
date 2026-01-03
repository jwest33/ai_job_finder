"""
Resume Parser - Uses LLM with Pydantic schema enforcement to parse resumes

Extracts structured data from plain text resumes using AI with
guaranteed output schema via Pydantic models.
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from .llama_client import LlamaClient, get_llama_client


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
# Resume Parser Class
# ============================================================================

class ResumeParser:
    """
    Parses resume text into structured data using LLM with Pydantic schema enforcement.
    """

    PARSING_PROMPT = """You are an expert resume parser. Extract structured information from the following resume text.

RESUME TEXT:
---
{resume_text}
---

INSTRUCTIONS:
1. Extract ALL information present in the resume
2. For contact info, look for name (usually at top), email, phone, location, LinkedIn, website
3. For experience, extract each job with title, company, dates, location, and bullet points
4. For education, extract degree, school, year, GPA if present, honors
5. For skills, extract all technical and soft skills mentioned
6. If a field is not present in the resume, leave it as empty string or empty list
7. Preserve the original wording from the resume for bullet points and descriptions
8. Dates should be in their original format (e.g., "Jan 2020", "2020", "January 2020 - Present")

IMPORTANT: Return ONLY valid JSON matching the exact schema provided. No explanations."""

    def __init__(self, client: Optional[LlamaClient] = None):
        """
        Initialize Resume Parser

        Args:
            client: Optional LlamaClient instance. If not provided, creates one.
        """
        self.client = client or get_llama_client()
        # Generate JSON schema from Pydantic model
        self.json_schema = ParsedResume.model_json_schema()

    def parse(self, resume_text: str) -> Optional[ParsedResume]:
        """
        Parse resume text into structured data

        Args:
            resume_text: Plain text resume content

        Returns:
            ParsedResume object with extracted data, or None if parsing fails
        """
        if not resume_text or not resume_text.strip():
            return None

        prompt = self.PARSING_PROMPT.format(resume_text=resume_text)

        # Call LLM with JSON schema enforcement
        result = self.client.generate_json(
            prompt=prompt,
            temperature=0.1,  # Low temperature for consistent extraction
            max_tokens=4096,  # Resumes can be long
            json_schema=self.json_schema
        )

        if not result:
            return None

        try:
            # Validate and parse using Pydantic
            return ParsedResume.model_validate(result)
        except Exception as e:
            print(f"[ERROR] Failed to validate parsed resume: {e}")
            return None

    def test_connection(self) -> bool:
        """Test if the AI server is available"""
        return self.client.test_connection()


def get_resume_parser() -> ResumeParser:
    """Get a ResumeParser instance"""
    return ResumeParser()


# ============================================================================
# Serialization helpers
# ============================================================================

def serialize_resume_to_text(data: ParsedResume) -> str:
    """
    Convert ParsedResume back to plain text format

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
                    lines.append(f"• {bullet}")

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
            lines.append(f"• {cert}")
        lines.append("")

    # Languages
    if data.languages:
        lines.append("LANGUAGES")
        lines.append("")
        lines.append(", ".join(data.languages))

    return "\n".join(lines).strip()


if __name__ == "__main__":
    # Test the parser
    print("Testing Resume Parser...")
    parser = ResumeParser()

    if parser.test_connection():
        print("Connection successful!")

        sample_resume = """
John Smith
john.smith@email.com | (555) 123-4567 | New York, NY
linkedin.com/in/johnsmith

Experienced software engineer with 5+ years building scalable web applications.

EXPERIENCE

Senior Software Engineer | Tech Corp | Jan 2022 - Present | San Francisco, CA
• Led development of microservices architecture serving 10M+ users
• Reduced API latency by 40% through database optimization
• Mentored team of 3 junior developers

Software Engineer | StartupXYZ | Jun 2019 - Dec 2021 | New York, NY
• Built real-time data pipeline processing 1M events/day
• Implemented CI/CD pipelines reducing deployment time by 60%

EDUCATION

B.S. Computer Science, MIT, 2019
GPA: 3.8, Magna Cum Laude

SKILLS

Python, JavaScript, TypeScript, React, Node.js, PostgreSQL, AWS, Docker, Kubernetes

CERTIFICATIONS

• AWS Solutions Architect
• Google Cloud Professional

LANGUAGES

English (Native), Spanish (Conversational)
"""

        print("\nParsing sample resume...")
        result = parser.parse(sample_resume)

        if result:
            print(f"\nName: {result.contact.name}")
            print(f"Email: {result.contact.email}")
            print(f"Phone: {result.contact.phone}")
            print(f"\nExperience entries: {len(result.experience)}")
            for job in result.experience:
                print(f"  - {job.title} at {job.company}")
            print(f"\nEducation entries: {len(result.education)}")
            print(f"Skills: {len(result.skills)}")
            print(f"Certifications: {len(result.certifications)}")
        else:
            print("Parsing failed!")
    else:
        print("Connection failed. Is llama-server running?")
