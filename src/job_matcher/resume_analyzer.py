"""
ResumeAnalyzer - Parse and manage resume and requirements

Handles loading resumes from various formats (TXT, PDF, DOCX) and
parsing requirements from YAML configuration.
"""

import os
import sys
import yaml
from typing import Optional, Dict, List, Any
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for profile_manager import
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.profile_manager import ProfilePaths

# Optional imports for different file formats
try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

load_dotenv()


class ResumeAnalyzer:
    """Parse and analyze resume and candidate profile"""

    def __init__(
        self,
        resume_path: Optional[str] = None,
        requirements_path: Optional[str] = None,
        profile_name: Optional[str] = None,
    ):
        """
        Initialize ResumeAnalyzer

        Args:
            resume_path: Path to resume file (default: from profile)
            requirements_path: Path to candidate profile YAML (default: from profile)
            profile_name: Profile name (default: from .env ACTIVE_PROFILE)
        """
        # Get profile paths
        paths = ProfilePaths(profile_name)

        # Use profile paths as defaults, or custom paths if provided
        self.resume_path = resume_path or os.getenv(
            "RESUME_PATH", str(paths.resume_path)
        )
        self.requirements_path = requirements_path or os.getenv(
            "REQUIREMENTS_PATH", str(paths.requirements_path)
        )

        self.resume_text = None
        self.candidate_profile = None
        self.preferences = None

    def load_resume(self, path: Optional[str] = None) -> str:
        """
        Load resume from file

        Args:
            path: Path to resume file (default: self.resume_path)

        Returns:
            Resume text content

        Raises:
            FileNotFoundError: If resume file doesn't exist
            ValueError: If file format is not supported
        """
        path = path or self.resume_path
        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"Resume file not found: {path}")

        # Determine file type and load accordingly
        extension = file_path.suffix.lower()

        if extension == ".txt":
            self.resume_text = self._load_text(file_path)
        elif extension == ".pdf":
            self.resume_text = self._load_pdf(file_path)
        elif extension in [".docx", ".doc"]:
            self.resume_text = self._load_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {extension}")

        return self.resume_text

    def _load_text(self, file_path: Path) -> str:
        """Load plain text file"""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def _load_pdf(self, file_path: Path) -> str:
        """Load PDF file"""
        if not PDF_AVAILABLE:
            raise ImportError(
                "PyPDF2 is required to read PDF files. Install with: pip install PyPDF2"
            )

        text_parts = []
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page in pdf_reader.pages:
                text_parts.append(page.extract_text())

        return "\n\n".join(text_parts)

    def _load_docx(self, file_path: Path) -> str:
        """Load DOCX file"""
        if not DOCX_AVAILABLE:
            raise ImportError(
                "python-docx is required to read DOCX files. Install with: pip install python-docx"
            )

        doc = docx.Document(file_path)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n\n".join(paragraphs)

    def load_requirements(self, path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load job requirements from YAML file

        Args:
            path: Path to job requirements YAML (default: self.requirements_path)

        Returns:
            Dict with 'job_requirements' and 'preferences' keys

        Raises:
            FileNotFoundError: If requirements file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        path = path or self.requirements_path
        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"Job requirements file not found: {path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Support both old 'candidate_profile' and new 'job_requirements' structure
        self.candidate_profile = data.get("job_requirements", data.get("candidate_profile", {}))
        self.preferences = data.get("preferences", {})

        print(f'candidate_profile loaded: {self.candidate_profile}')

        return {"candidate_profile": self.candidate_profile, "preferences": self.preferences}

    def get_requirements_text(self) -> str:
        """
        Format job requirements as readable text for AI prompts.

        Structures output to clearly separate:
        1. DEAL-BREAKERS (must_haves, avoid) - Hard requirements that disqualify jobs
        2. PREFERENCES (target_roles, skills, career_goals) - Nice-to-haves that boost score

        Returns:
            Formatted job requirements text
        """
        if not self.candidate_profile:
            return "No job requirements specified."

        lines = []

        # ============================================================
        # SECTION 1: DEAL-BREAKERS (These are the ONLY hard requirements)
        # ============================================================
        lines.append("=" * 60)
        lines.append("DEAL-BREAKERS (HARD REQUIREMENTS - THESE ARE THE ONLY DISQUALIFIERS)")
        lines.append("=" * 60)
        lines.append("")
        lines.append("The following are the ONLY criteria that should disqualify a job.")
        lines.append("Missing skills or not matching preferences should NOT disqualify a job.")
        lines.append("")

        # Must-Haves (Deal-Breakers)
        must_haves = self.candidate_profile.get("must_haves", [])
        if must_haves:
            lines.append("MUST-HAVES (Job MUST have ALL of these or score capped at 49):")
            for item in must_haves:
                lines.append(f"  * {item}")
            lines.append("")

        # Things to Avoid
        avoid = self.candidate_profile.get("avoid", [])
        if avoid:
            lines.append("AVOID (Job must NOT have ANY of these or score capped at 49):")
            for item in avoid:
                lines.append(f"  * {item}")
            lines.append("")

        # ============================================================
        # SECTION 2: PREFERENCES (Nice-to-haves that boost score)
        # ============================================================
        lines.append("=" * 60)
        lines.append("PREFERENCES (NICE-TO-HAVES - DO NOT DISQUALIFY JOBS FOR MISSING THESE)")
        lines.append("=" * 60)
        lines.append("")
        lines.append("The following are preferences that should POSITIVELY influence the score")
        lines.append("if matched, but should NOT disqualify jobs if missing.")
        lines.append("")

        # Target Roles
        target_roles = self.candidate_profile.get("target_roles", [])
        if target_roles:
            lines.append("Target Roles (preferred job titles):")
            for role in target_roles:
                lines.append(f"  - {role}")
            lines.append("")

        # Skills (soft preferences)
        skills = self.candidate_profile.get("skills", {})
        if isinstance(skills, dict):
            preferred_skills = skills.get("preferred", [])

            if preferred_skills:
                lines.append("Preferred Skills (bonus points if job uses these, but NOT required):")
                for skill in preferred_skills:
                    lines.append(f"  - {skill}")
                lines.append("")

        # Career Goals (what they're looking for)
        career_goals = self.candidate_profile.get("career_goals", "").strip()
        if career_goals:
            lines.append("Career Goals (ideal role description):")
            lines.append(career_goals)
            lines.append("")

        return "\n".join(lines)

    def get_preferences_text(self) -> str:
        """
        Format preferences as readable text for AI prompts

        Returns:
            Formatted preferences text
        """
        if not self.preferences:
            return "No preferences specified."

        lines = ["Job Preferences:"]

        if self.preferences.get("remote_only"):
            lines.append("  - Remote work: REQUIRED")

        if "min_salary" in self.preferences:
            min_sal = self.preferences["min_salary"]
            period = self.preferences.get("salary_period", "yearly")
            lines.append(f"  - Minimum salary: ${min_sal:,} {period}")

        if "max_salary" in self.preferences:
            max_sal = self.preferences["max_salary"]
            period = self.preferences.get("salary_period", "yearly")
            lines.append(f"  - Maximum salary: ${max_sal:,} {period}")

        if "locations" in self.preferences:
            locations = ", ".join(self.preferences["locations"])
            lines.append(f"  - Preferred locations: {locations}")

        return "\n".join(lines)

    def validate_job_preferences(self, job: Dict[str, Any]) -> Dict[str, bool]:
        """
        Check if job meets preferences

        Args:
            job: Job dict from JobPost

        Returns:
            Dict with preference checks (True if met, False if not)
        """
        checks = {}

        if not self.preferences:
            return checks

        # Check remote requirement
        if self.preferences.get("remote_only"):
            checks["remote"] = job.get("remote", False)

        # Check salary
        if "min_salary" in self.preferences:
            job_min = job.get("salary_min")
            if job_min:
                # Defensive type conversion: handle string/int/float salary values
                try:
                    job_min = float(job_min)
                    checks["min_salary"] = job_min >= self.preferences["min_salary"]
                except (TypeError, ValueError):
                    # If conversion fails, skip salary check
                    pass

        if "max_salary" in self.preferences:
            job_max = job.get("salary_max")
            if job_max:
                # Defensive type conversion: handle string/int/float salary values
                try:
                    job_max = float(job_max)
                    checks["max_salary"] = job_max <= self.preferences["max_salary"]
                except (TypeError, ValueError):
                    # If conversion fails, skip salary check
                    pass

        # Check location
        if "locations" in self.preferences:
            job_location = job.get("location", "")
            preferred_locations = self.preferences["locations"]
            checks["location"] = any(
                loc.lower() in job_location.lower() for loc in preferred_locations
            )

        return checks

    def load_all(self) -> bool:
        """
        Load both resume and requirements

        Returns:
            True if both loaded successfully, False otherwise
        """
        try:
            self.load_resume()
            self.load_requirements()
            return True
        except Exception as e:
            print(f"X Error loading files: {e}")
            return False


if __name__ == "__main__":
    # Test the analyzer
    print("Testing ResumeAnalyzer...")
    analyzer = ResumeAnalyzer()

    print(f"Resume path: {analyzer.resume_path}")
    print(f"Requirements path: {analyzer.requirements_path}")
    print()

    # Try to load files
    try:
        print("Loading resume...")
        resume = analyzer.load_resume()
        print(f"Resume loaded: {len(resume)} characters")
        print(f"First 200 chars: {resume[:200]}...")
    except Exception as e:
        print(f"⚠️  Could not load resume: {e}")

    print()

    try:
        print("Loading candidate profile...")
        profile = analyzer.load_requirements()
        print(f"Candidate profile loaded")
        print()
        print(analyzer.get_requirements_text())
        print()
        print(analyzer.get_preferences_text())
    except Exception as e:
        print(f"⚠️  Could not load candidate profile: {e}")

    print("\nResumeAnalyzer test complete")
