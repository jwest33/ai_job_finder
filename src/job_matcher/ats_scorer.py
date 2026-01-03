"""
ATS Quality Scorer - Evaluates resumes for ATS compatibility

Analyzes resumes against common ATS (Applicant Tracking System) requirements
and provides scores with actionable recommendations.
"""

import json
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from .llama_client import LlamaClient, get_llama_client


@dataclass
class ATSCategory:
    """Score and feedback for a single ATS category"""
    score: int
    issues: list
    recommendations: list


@dataclass
class ATSScoreResult:
    """Complete ATS scoring result"""
    overall_score: int
    categories: Dict[str, ATSCategory]
    summary: str
    top_recommendations: list

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "overall_score": self.overall_score,
            "categories": {
                name: asdict(cat) for name, cat in self.categories.items()
            },
            "summary": self.summary,
            "top_recommendations": self.top_recommendations
        }


class ATSScorer:
    """
    Evaluates resumes for ATS (Applicant Tracking System) compatibility.

    Uses AI to analyze resumes against common ATS requirements including:
    - Keyword optimization
    - Formatting compatibility
    - Section structure
    - Quantified achievements
    - Contact information
    - Skills presentation
    """

    SCORING_PROMPT = """You are an expert ATS (Applicant Tracking System) analyst. Your task is to evaluate a resume for ATS compatibility and provide detailed scoring with actionable recommendations.

RESUME TO ANALYZE:
---
{resume_content}
---

EVALUATION CRITERIA:

1. KEYWORDS (0-100 points)
   - Industry-standard terminology usage
   - Action verbs and power words
   - Technical skills properly listed
   - Avoid creative synonyms that ATS won't recognize

2. FORMATTING (0-100 points)
   - Simple, clean structure (no tables, columns, graphics)
   - Standard fonts and sizes
   - Consistent date formats
   - No headers/footers with critical info
   - Bullet points using standard characters

3. SECTIONS (0-100 points)
   - Clear section headers (Experience, Education, Skills, etc.)
   - Logical ordering
   - Standard section names (not creative alternatives)
   - Complete required sections

4. ACHIEVEMENTS (0-100 points)
   - Quantified results with numbers/percentages
   - Specific accomplishments vs generic duties
   - Impact statements with measurable outcomes
   - STAR format adherence (Situation, Task, Action, Result)

5. CONTACT_INFO (0-100 points)
   - Complete contact details (name, phone, email, location)
   - Professional email address
   - LinkedIn URL if relevant
   - Proper placement at top of resume

6. SKILLS (0-100 points)
   - Dedicated skills section
   - Hard skills clearly listed
   - Skill categories organized
   - Avoids soft skills without context
   - Technical proficiencies specified

SCORING GUIDELINES:
- 90-100: Excellent - Ready for submission
- 70-89: Good - Minor improvements needed
- 50-69: Fair - Several issues to address
- 30-49: Poor - Major revisions required
- 0-29: Critical - Complete rewrite recommended

RESPOND WITH ONLY THIS JSON STRUCTURE:
{{
    "overall_score": <weighted average 0-100>,
    "categories": {{
        "keywords": {{
            "score": <0-100>,
            "issues": ["issue1", "issue2"],
            "recommendations": ["rec1", "rec2"]
        }},
        "formatting": {{
            "score": <0-100>,
            "issues": ["issue1", "issue2"],
            "recommendations": ["rec1", "rec2"]
        }},
        "sections": {{
            "score": <0-100>,
            "issues": ["issue1", "issue2"],
            "recommendations": ["rec1", "rec2"]
        }},
        "achievements": {{
            "score": <0-100>,
            "issues": ["issue1", "issue2"],
            "recommendations": ["rec1", "rec2"]
        }},
        "contact_info": {{
            "score": <0-100>,
            "issues": ["issue1", "issue2"],
            "recommendations": ["rec1", "rec2"]
        }},
        "skills": {{
            "score": <0-100>,
            "issues": ["issue1", "issue2"],
            "recommendations": ["rec1", "rec2"]
        }}
    }},
    "summary": "<2-3 sentence overall assessment>",
    "top_recommendations": ["<top 3-5 most impactful improvements>"]
}}

CRITICAL: Respond with ONLY the JSON object. No explanations, no thinking, no text outside the JSON."""

    JSON_SCHEMA = {
        "type": "object",
        "properties": {
            "overall_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "categories": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "object",
                        "properties": {
                            "score": {"type": "integer"},
                            "issues": {"type": "array", "items": {"type": "string"}},
                            "recommendations": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["score", "issues", "recommendations"]
                    },
                    "formatting": {
                        "type": "object",
                        "properties": {
                            "score": {"type": "integer"},
                            "issues": {"type": "array", "items": {"type": "string"}},
                            "recommendations": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["score", "issues", "recommendations"]
                    },
                    "sections": {
                        "type": "object",
                        "properties": {
                            "score": {"type": "integer"},
                            "issues": {"type": "array", "items": {"type": "string"}},
                            "recommendations": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["score", "issues", "recommendations"]
                    },
                    "achievements": {
                        "type": "object",
                        "properties": {
                            "score": {"type": "integer"},
                            "issues": {"type": "array", "items": {"type": "string"}},
                            "recommendations": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["score", "issues", "recommendations"]
                    },
                    "contact_info": {
                        "type": "object",
                        "properties": {
                            "score": {"type": "integer"},
                            "issues": {"type": "array", "items": {"type": "string"}},
                            "recommendations": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["score", "issues", "recommendations"]
                    },
                    "skills": {
                        "type": "object",
                        "properties": {
                            "score": {"type": "integer"},
                            "issues": {"type": "array", "items": {"type": "string"}},
                            "recommendations": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["score", "issues", "recommendations"]
                    }
                },
                "required": ["keywords", "formatting", "sections", "achievements", "contact_info", "skills"]
            },
            "summary": {"type": "string"},
            "top_recommendations": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["overall_score", "categories", "summary", "top_recommendations"]
    }

    def __init__(self, client: Optional[LlamaClient] = None):
        """
        Initialize ATS Scorer

        Args:
            client: Optional LlamaClient instance. If not provided, creates one.
        """
        self.client = client or get_llama_client()

    def score_resume(self, resume_content: str) -> Optional[ATSScoreResult]:
        """
        Score a resume for ATS compatibility

        Args:
            resume_content: Plain text resume content

        Returns:
            ATSScoreResult with scores and recommendations, or None if scoring fails
        """
        if not resume_content or not resume_content.strip():
            return None

        # Build prompt
        prompt = self.SCORING_PROMPT.format(resume_content=resume_content)

        # Call LlamaClient with JSON schema
        result = self.client.generate_json(
            prompt=prompt,
            temperature=0.3,  # Low temperature for consistent scoring
            max_tokens=2048,
            json_schema=self.JSON_SCHEMA
        )

        if not result:
            return None

        # Parse and validate result
        try:
            categories = {}
            for cat_name in ["keywords", "formatting", "sections", "achievements", "contact_info", "skills"]:
                cat_data = result.get("categories", {}).get(cat_name, {})
                categories[cat_name] = ATSCategory(
                    score=cat_data.get("score", 0),
                    issues=cat_data.get("issues", []),
                    recommendations=cat_data.get("recommendations", [])
                )

            return ATSScoreResult(
                overall_score=result.get("overall_score", 0),
                categories=categories,
                summary=result.get("summary", ""),
                top_recommendations=result.get("top_recommendations", [])
            )
        except Exception as e:
            print(f"[ERROR] Failed to parse ATS score result: {e}")
            return None

    def test_connection(self) -> bool:
        """Test if the AI server is available"""
        return self.client.test_connection()


def get_ats_scorer() -> ATSScorer:
    """Get an ATSScorer instance"""
    return ATSScorer()


if __name__ == "__main__":
    # Test the scorer
    print("Testing ATS Scorer...")
    scorer = ATSScorer()

    if scorer.test_connection():
        print("Connection successful!")

        # Test with a sample resume
        sample_resume = """
John Smith
john.smith@email.com | (555) 123-4567 | New York, NY

EXPERIENCE

Software Engineer | Tech Company | 2020-Present
- Developed web applications using Python and JavaScript
- Collaborated with team members on projects
- Fixed bugs and improved code quality

Junior Developer | Startup Inc | 2018-2020
- Worked on various coding tasks
- Helped with testing

EDUCATION
Bachelor of Science in Computer Science
State University, 2018

SKILLS
Python, JavaScript, SQL, Git
"""

        print("\nScoring sample resume...")
        result = scorer.score_resume(sample_resume)

        if result:
            print(f"\nOverall Score: {result.overall_score}/100")
            print(f"\nSummary: {result.summary}")
            print("\nCategory Scores:")
            for name, cat in result.categories.items():
                print(f"  {name}: {cat.score}/100")
            print("\nTop Recommendations:")
            for rec in result.top_recommendations:
                print(f"  - {rec}")
        else:
            print("Scoring failed!")
    else:
        print("Connection failed. Is llama-server running?")
