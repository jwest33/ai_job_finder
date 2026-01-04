"""
Comparison Engine - Hybrid Scoring System

Combines deterministic scoring (40%) with AI-based scoring (60%) for
more accurate and explainable job matching.
"""

from typing import Dict, Any, List, Tuple, Optional
from .models.job_sections import extract_job_sections, JobComparison


class ComparisonEngine:
    """Hybrid scoring engine combining deterministic and AI-based scores"""

    def __init__(self, candidate_requirements: Dict[str, Any], preferences: Dict[str, Any]):
        """
        Initialize ComparisonEngine

        Args:
            candidate_requirements: Candidate requirements from YAML
            preferences: Job preferences from YAML
        """
        self.requirements = candidate_requirements if candidate_requirements is not None else {}
        self.preferences = preferences if preferences is not None else {}

    def calculate_deterministic_score(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate deterministic score (0-40 points) based on hard requirements

        Breakdown:
        - Title match: 0-20 points (weighted higher - most important filter)
        - Salary match: 0-10 points
        - Location/remote match: 0-10 points

        Args:
            job: Raw job dictionary

        Returns:
            Dict with score breakdown and total deterministic_score
        """
        job_sections = extract_job_sections(job)

        scores = {
            'title_score': self._score_title_match(job_sections),
            'salary_score': self._score_salary_match(job_sections),
            'location_score': self._score_location_match(job_sections),
        }

        # Calculate total (max 40 points)
        total_score = sum(scores.values())

        return {
            **scores,
            'deterministic_score': total_score,
            'max_deterministic_score': 40,
        }

    def _score_title_match(self, job: JobComparison) -> float:
        """
        Score title match (0-20 points)

        Scoring logic:
        - Exact role match (e.g., "Senior Data Engineer"): 20 points
        - Strong match with domain keyword (e.g., "Data Platform Engineer"): 15-18 points
        - Partial match with domain keyword (e.g., "Data Engineer"): 12-15 points
        - Generic title with some keywords (e.g., "Staff Engineer"): 5-8 points
        - No relevant keywords: 0 points

        Returns:
            Score from 0 to 20
        """
        if not job.title:
            return 5.0  # Neutral score if no title

        title_lower = job.title.job_title.lower()

        # Get target roles and keywords
        target_roles = self.requirements.get('target_roles', [])
        related_keywords = self.requirements.get('related_keywords', [])

        # Check for exact role match first (highest score)
        for role in target_roles:
            role_lower = role.lower()
            if role_lower in title_lower or title_lower in role_lower:
                return 20.0  # Exact match

        # Extract domain-specific keywords (the core of what the role is about)
        # These are critical - without them, the title is too ambiguous
        domain_keywords = set()
        generic_keywords = set()
        seniority_keywords = {'senior', 'staff', 'lead', 'principal', 'junior', 'associate', 'head', 'director', 'manager', 'vp'}

        for role in target_roles:
            words = role.lower().split()
            for word in words:
                if word in seniority_keywords:
                    continue  # Skip seniority modifiers
                elif word in {'engineer', 'developer', 'architect', 'analyst', 'scientist'}:
                    generic_keywords.add(word)  # Generic role words
                else:
                    domain_keywords.add(word)  # Domain-specific (e.g., "data", "platform", "infrastructure")

        # Add related keywords as domain keywords
        for kw in related_keywords:
            kw_lower = kw.lower()
            if kw_lower not in seniority_keywords and kw_lower not in generic_keywords:
                domain_keywords.add(kw_lower)

        # Count matches
        domain_matches = sum(1 for kw in domain_keywords if kw in title_lower)
        generic_matches = sum(1 for kw in generic_keywords if kw in title_lower)
        seniority_matches = sum(1 for kw in seniority_keywords if kw in title_lower)

        # Scoring logic - domain keywords are critical
        if domain_matches >= 2:
            # Strong domain match (e.g., "Data Platform Engineer")
            base_score = 16.0
            base_score += min(generic_matches * 1.5, 3.0)  # Bonus for generic matches
            base_score += min(seniority_matches * 0.5, 1.0)  # Small bonus for seniority
            return min(base_score, 20.0)
        elif domain_matches == 1:
            # Single domain keyword match (e.g., "Data Engineer")
            base_score = 12.0
            base_score += min(generic_matches * 1.5, 3.0)
            base_score += min(seniority_matches * 0.5, 1.0)
            return min(base_score, 17.0)
        elif generic_matches >= 1:
            # Only generic keywords match (e.g., "Staff Engineer" - ambiguous!)
            # This is penalized because we don't know what KIND of engineer
            base_score = 4.0
            base_score += min(seniority_matches * 1.0, 2.0)
            return min(base_score, 6.0)
        else:
            # No relevant matches
            return 0.0

    def _score_salary_match(self, job: JobComparison) -> float:
        """
        Score salary match (0-10 points)

        Returns:
            Score from 0 to 10
        """
        if not job.compensation:
            return 5.0  # Neutral if no salary info

        min_salary_required = self.preferences.get('min_salary')
        max_salary_required = self.preferences.get('max_salary')

        if not min_salary_required:
            return 5.0  # Neutral if no salary requirement

        job_salary_max = job.compensation.salary_max
        job_salary_min = job.compensation.salary_min

        if not job_salary_max and not job_salary_min:
            return 5.0  # Neutral if no salary info

        # Use salary midpoint for comparison
        salary_midpoint = job.compensation.get_salary_midpoint()
        if not salary_midpoint:
            return 5.0

        # Calculate score based on how well salary aligns
        if salary_midpoint < min_salary_required:
            # Below minimum - lower score
            diff_percent = (min_salary_required - salary_midpoint) / min_salary_required
            if diff_percent > 0.2:  # More than 20% below
                return 0.0
            elif diff_percent > 0.1:  # 10-20% below
                return 3.0
            else:  # Less than 10% below
                return 6.0
        elif max_salary_required and salary_midpoint > max_salary_required:
            # Above maximum (usually still good)
            return 8.0
        else:
            # Within range - perfect score
            return 10.0

    def _score_location_match(self, job: JobComparison) -> float:
        """
        Score location/remote match (0-10 points)

        Returns:
            Score from 0 to 10
        """
        if not job.work:
            return 5.0  # Neutral if no work info

        remote_required = self.preferences.get('remote_only', False)
        preferred_locations = self.preferences.get('locations', [])

        # If remote required
        if remote_required:
            if job.work.remote:
                return 10.0  # Perfect match
            else:
                return 0.0  # Fails requirement

        # If remote not required, check location preferences
        if not preferred_locations:
            return 5.0  # Neutral if no preferences

        # Remote job always matches
        if job.work.remote:
            return 10.0

        # Check if location matches any preferred location
        job_location = job.work.location.lower()
        for location in preferred_locations:
            if location.lower() in job_location:
                return 10.0

        return 3.0  # Location doesn't match, but not a dealbreaker

    def combine_scores(
        self,
        deterministic_scores: Dict[str, Any],
        ai_score: int,
        ai_reasoning: str
    ) -> Dict[str, Any]:
        """
        Combine deterministic and AI scores into final hybrid score

        Weighting:
        - Deterministic: 40% (max 40 points) - Title (20), Salary (10), Location (10)
        - AI: 60% (max 60 points) - Overall fit, qualifications, experience

        Args:
            deterministic_scores: Dict with deterministic score breakdown
            ai_score: AI-generated score (0-100)
            ai_reasoning: AI reasoning text

        Returns:
            Dict with combined score and breakdown
        """
        # AI score is 0-100, convert to 0-60 for weighting
        ai_weighted_score = (ai_score / 100) * 60

        # Deterministic score is 0-40 (Title: 20, Salary: 10, Location: 10)
        deterministic_total = deterministic_scores['deterministic_score']

        # Combined score (0-100)
        combined_score = deterministic_total + ai_weighted_score

        return {
            'combined_score': round(combined_score, 1),
            'deterministic_component': deterministic_total,
            'ai_component': round(ai_weighted_score, 1),
            'original_ai_score': ai_score,
            'deterministic_breakdown': {
                'title': deterministic_scores['title_score'],
                'salary': deterministic_scores['salary_score'],
                'location': deterministic_scores['location_score'],
            },
            'ai_reasoning': ai_reasoning,
        }

    def get_section_comparison(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get detailed section-by-section comparison for a job

        Args:
            job: Raw job dictionary

        Returns:
            Dict with structured section comparisons
        """
        job_sections = extract_job_sections(job)

        comparison = {
            'title_analysis': self._compare_title_section(job_sections),
            'requirements_analysis': self._compare_requirements_section(job_sections),
            'compensation_analysis': self._compare_compensation_section(job_sections),
            'work_analysis': self._compare_work_section(job_sections),
            'company_analysis': self._compare_company_section(job_sections),
        }

        return comparison

    def _compare_title_section(self, job: JobComparison) -> Dict[str, Any]:
        """Compare title section with requirements"""
        if not job.title:
            return {}

        return {
            'job_title': job.title.job_title,
            'seniority_level': job.title.seniority_level,
            'job_family': job.title.job_family,
        }

    def _compare_requirements_section(self, job: JobComparison) -> Dict[str, Any]:
        """Compare requirements section"""
        if not job.requirements:
            return {}

        # Get candidate skills
        candidate_skills = self.requirements.get('skills', {})
        if isinstance(candidate_skills, dict):
            required_skills = [s.lower() for s in candidate_skills.get('required', [])]
            preferred_skills = [s.lower() for s in candidate_skills.get('preferred', [])]
        else:
            required_skills = []
            preferred_skills = []

        # Get job skills
        job_skills = [s.lower() for s in job.requirements.skills]

        # Calculate matches
        required_matches = [s for s in required_skills if any(s in js for js in job_skills)]
        preferred_matches = [s for s in preferred_skills if any(s in js for js in job_skills)]

        return {
            'job_skills': job.requirements.skills,
            'candidate_required_skills': required_skills,
            'candidate_preferred_skills': preferred_skills,
            'required_skill_matches': required_matches,
            'preferred_skill_matches': preferred_matches,
            'required_match_percent': len(required_matches) / len(required_skills) if required_skills else 0,
            'experience_years': job.requirements.experience_years_min,
        }

    def _compare_compensation_section(self, job: JobComparison) -> Dict[str, Any]:
        """Compare compensation section"""
        if not job.compensation:
            return {}

        return {
            'salary_range': f"${job.compensation.salary_min:,.0f} - ${job.compensation.salary_max:,.0f}" if job.compensation.salary_min else "Not specified",
            'salary_midpoint': job.compensation.get_salary_midpoint(),
            'required_min_salary': self.preferences.get('min_salary'),
            'meets_salary_requirement': job.compensation.get_salary_midpoint() >= self.preferences.get('min_salary', 0) if job.compensation.get_salary_midpoint() else None,
            'has_equity': job.compensation.has_equity,
            'has_bonus': job.compensation.has_bonus,
            'benefits_count': len(job.compensation.benefits),
        }

    def _compare_work_section(self, job: JobComparison) -> Dict[str, Any]:
        """Compare work arrangements section"""
        if not job.work:
            return {}

        return {
            'remote': job.work.remote,
            'remote_policy': job.work.remote_policy,
            'location': job.work.location,
            'job_type': job.work.job_type,
            'remote_required': self.preferences.get('remote_only', False),
            'meets_remote_requirement': job.work.remote if self.preferences.get('remote_only', False) else True,
        }

    def _compare_company_section(self, job: JobComparison) -> Dict[str, Any]:
        """Compare company section"""
        if not job.company:
            return {}

        preferred_sizes = self.requirements.get('company_sizes', [])
        company_size_category = job.company.get_size_category()

        return {
            'company_name': job.company.company_name,
            'company_size': job.company.company_size,
            'company_size_category': company_size_category,
            'preferred_sizes': preferred_sizes,
            'matches_size_preference': company_size_category in [s.lower() for s in preferred_sizes] if preferred_sizes else True,
            'has_description': bool(job.company.company_description),
        }
