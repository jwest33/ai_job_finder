"""
MatchScorer - Pass 1: Initial Job Matching

Analyzes jobs against resume and requirements to generate match scores.
Supports multi-threaded processing for faster batch scoring.
"""

import json
import os
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, List
from .llama_client import LlamaClient
from .resume_analyzer import ResumeAnalyzer
from .failure_tracker import FailureTracker, ErrorType
from .filters import apply_filters_to_jobs
from .comparison_engine import ComparisonEngine
from .models.job_sections import extract_job_sections
from .smooth_batch_processor import SmoothBatchProcessor


class MatchScorer:
    """Score jobs based on resume and requirements match"""

    def __init__(
        self, llama_client: LlamaClient, resume_analyzer: ResumeAnalyzer,
        checkpoint_manager=None, failure_tracker: Optional[FailureTracker] = None
    ):
        """
        Initialize MatchScorer

        Args:
            llama_client: LlamaClient instance for AI generation
            resume_analyzer: ResumeAnalyzer instance with loaded resume/requirements
            checkpoint_manager: Optional CheckpointManager for resume support
            failure_tracker: Optional FailureTracker for tracking failed jobs
        """
        self.client = llama_client
        self.analyzer = resume_analyzer
        self.checkpoint_manager = checkpoint_manager
        self.failure_tracker = failure_tracker
        self.failed_jobs: List[Dict[str, Any]] = []  # Track failures during batch
        self.rejected_jobs: List[Dict[str, Any]] = []  # Track title-rejected jobs
        self.filtered_jobs: List[Dict[str, Any]] = []  # Track pre-filtered jobs

        # Initialize comparison engine for hybrid scoring
        self.comparison_engine = ComparisonEngine(
            self.analyzer.candidate_profile,
            self.analyzer.preferences
        )

    def _extract_title_keywords(self) -> List[str]:
        """
        Extract target role keywords from requirements

        Returns:
            List of keywords (lowercased) for title matching
        """
        keywords = []

        # Get target roles from candidate profile
        target_roles = self.analyzer.candidate_profile.get("target_roles", [])
        related_keywords = self.analyzer.candidate_profile.get("related_keywords", [])

        # Extract keywords from target roles (individual words)
        for role in target_roles:
            # Split role into words and add them
            words = role.lower().split()
            keywords.extend(words)

        # Add related keywords
        for keyword in related_keywords:
            keywords.append(keyword.lower())

        # Remove common words that don't add value
        stop_words = {"and", "or", "the", "a", "an", "for", "to", "of", "in", "with"}
        keywords = [k for k in keywords if k not in stop_words]

        # Remove duplicates
        return list(set(keywords))

    def _is_title_relevant(self, job: Dict[str, Any]) -> bool:
        """
        Check if job title is relevant based on target keywords

        Args:
            job: Job dict with title field

        Returns:
            True if title contains any target keywords, False otherwise
        """
        job_title = job.get("title", "").lower()
        keywords = self._extract_title_keywords()

        # If no keywords defined, accept all jobs (fallback)
        if not keywords:
            return True

        # Check if job title contains ANY of the keywords
        for keyword in keywords:
            if keyword in job_title:
                return True

        return False

    def score_job(self, job: Dict[str, Any], use_hybrid_scoring: bool = True) -> Optional[Dict[str, Any]]:
        """
        Score a single job against the resume and requirements

        Args:
            job: Job dict from JobPost
            use_hybrid_scoring: If True, combines deterministic + AI scores (default: True)

        Returns:
            Dict with match_score, reasoning, and preference_checks
            Returns None if scoring fails
        """
        try:
            # Calculate deterministic score first
            try:
                deterministic_scores = self.comparison_engine.calculate_deterministic_score(job)
            except Exception as det_error:
                error_msg = f"Deterministic scoring failed: {type(det_error).__name__}: {str(det_error)}"
                print(f"[WARNING] {error_msg}")
                print(f"   Job: {job.get('title', 'Unknown')}")
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "scoring", ErrorType.UNKNOWN_ERROR, error_msg)
                return None

            # Create scoring prompt
            try:
                prompt = self._create_scoring_prompt(job)
            except Exception as prompt_error:
                error_msg = f"Prompt creation failed: {type(prompt_error).__name__}: {str(prompt_error)}"
                print(f"[WARNING] {error_msg}")
                print(f"   Job: {job.get('title', 'Unknown')}")
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "scoring", ErrorType.UNKNOWN_ERROR, error_msg)
                return None

            # Define JSON schema for the expected response
            json_schema = {
                "type": "object",
                "properties": {
                    "match_score": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Match score from 0 to 100"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Brief explanation of the score (2-3 sentences)"
                    },
                    "matched_requirements": {
                        "type": "object",
                        "description": "Dictionary of matched requirements (can be empty)"
                    }
                },
                "required": ["match_score", "reasoning", "matched_requirements"]
            }

            # Generate response with JSON schema enforcement
            try:
                response = self.client.generate_json(
                    prompt,
                    temperature=0.2,  # Lower temperature for more consistent JSON output
                    max_tokens=2048,
                    json_schema=json_schema
                )
            except requests.exceptions.Timeout:
                error_msg = "Request timed out"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "scoring", ErrorType.TIMEOUT_ERROR, error_msg)
                print(f"[WARNING] Timeout scoring job: {job.get('title', 'Unknown')}")
                return None
            except requests.exceptions.ConnectionError as e:
                error_msg = f"Connection error: {str(e)}"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "scoring", ErrorType.CONNECTION_ERROR, error_msg)
                print(f"[WARNING] Connection error scoring job: {job.get('title', 'Unknown')}")
                return None
            except json.JSONDecodeError as e:
                error_msg = f"JSON parse error: {str(e)}"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "scoring", ErrorType.JSON_PARSE_ERROR, error_msg)
                print(f"[WARNING] JSON parse error scoring job: {job.get('title', 'Unknown')}")
                return None

            if not response or not isinstance(response, dict):
                error_msg = f"Invalid response from AI: {type(response).__name__}"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "scoring", ErrorType.UNKNOWN_ERROR, error_msg)
                print(f"[WARNING] Failed to score job: {job.get('title', 'Unknown')} - Invalid response type")
                return None

            # Extract AI score and reasoning
            ai_match_score = response.get("match_score", 0)
            ai_reasoning = response.get("reasoning", "No reasoning provided")
            matched_requirements = response.get("matched_requirements", {})

            # Validate AI score
            if not isinstance(ai_match_score, (int, float)) or ai_match_score < 0 or ai_match_score > 100:
                error_msg = f"Invalid match score: {ai_match_score}"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "scoring", ErrorType.VALIDATION_ERROR, error_msg)
                print(f"[WARNING] Invalid match score: {ai_match_score}, defaulting to 0")
                ai_match_score = 0

            # Combine deterministic and AI scores if hybrid scoring enabled
            if use_hybrid_scoring:
                combined = self.comparison_engine.combine_scores(
                    deterministic_scores,
                    int(ai_match_score),
                    ai_reasoning
                )
                final_score = int(combined['combined_score'])
                final_reasoning = f"[Hybrid Score: {final_score}/100 = Deterministic {combined['deterministic_component']:.0f} + AI {combined['ai_component']:.0f}]\n\n{ai_reasoning}"
            else:
                final_score = int(ai_match_score)
                final_reasoning = ai_reasoning

            # Check preferences
            preference_checks = self.analyzer.validate_job_preferences(job)

            result = {
                "match_score": final_score,
                "reasoning": final_reasoning,
                "matched_requirements": matched_requirements,
                "preference_checks": preference_checks,
            }

            # Add hybrid scoring breakdown if enabled
            if use_hybrid_scoring:
                result["scoring_breakdown"] = {
                    "deterministic_score": deterministic_scores['deterministic_score'],
                    "ai_score": int(ai_match_score),
                    "combined_score": final_score,
                    "deterministic_breakdown": deterministic_scores,
                }

            return result

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            if self.failure_tracker:
                self.failure_tracker.record_failure(job, "scoring", ErrorType.UNKNOWN_ERROR, error_msg)
            print(f"[WARNING] Unexpected error scoring job {job.get('title', 'Unknown')}: {e}")
            return None

    def _create_scoring_prompt(self, job: Dict[str, Any]) -> str:
        """
        Create AI prompt for job scoring with structured sections

        Args:
            job: Job dict from JobPost

        Returns:
            Formatted prompt string
        """
        # Extract structured job sections
        job_sections = extract_job_sections(job)

        # === TITLE SECTION ===
        title_text = f"""Title: {job_sections.title.job_title}
Seniority Level: {job_sections.title.seniority_level}
Job Family: {job_sections.title.job_family}"""

        # === REQUIREMENTS SECTION ===
        skills_list = "\n".join([f"  • {s}" for s in job_sections.requirements.skills]) if job_sections.requirements.skills else "  • Not specified"
        requirements_list = "\n".join([f"  • {r}" for r in job_sections.requirements.requirements]) if job_sections.requirements.requirements else "  • Not specified"

        experience_text = ""
        if job_sections.requirements.experience_years_min:
            experience_text = f"\nYears of Experience: {job_sections.requirements.experience_years_min}+"

        requirements_text = f"""Required Skills:
{skills_list}

Job Requirements:
{requirements_list}{experience_text}"""

        # === COMPENSATION SECTION ===
        salary_info = "Not specified"
        if job_sections.compensation.salary_min and job_sections.compensation.salary_max:
            salary_info = f"${job_sections.compensation.salary_min:,.0f} - ${job_sections.compensation.salary_max:,.0f} {job_sections.compensation.salary_currency} ({job_sections.compensation.salary_period})"

        benefits_list = "\n".join([f"  • {b}" for b in job_sections.compensation.benefits]) if job_sections.compensation.benefits else "  • Not specified"

        compensation_text = f"""Salary: {salary_info}
Equity: {"Yes" if job_sections.compensation.has_equity else "No"}
Bonus: {"Yes" if job_sections.compensation.has_bonus else "No"}

Benefits:
{benefits_list}"""

        # === WORK ARRANGEMENTS SECTION ===
        work_arrangements_list = "\n".join([f"  • {w}" for w in job_sections.work.work_arrangements]) if job_sections.work.work_arrangements else "  • Not specified"

        work_text = f"""Remote: {"Yes" if job_sections.work.remote else "No"}
Policy: {job_sections.work.remote_policy}
Location: {job_sections.work.location}
Job Type: {job_sections.work.job_type or "Not specified"}

Work Arrangements:
{work_arrangements_list}"""

        # === COMPANY SECTION ===
        company_description = job_sections.company.company_description or "Not available"

        # Add Glassdoor-specific fields
        company_rating_text = ""
        if job.get("company_rating"):
            company_rating_text = f"\nGlassdoor Rating: ⭐ {job['company_rating']:.1f}/5.0"

        easy_apply_text = ""
        if job.get("easy_apply"):
            easy_apply_text = "\n✓ Easy Apply Available (Quick application process)"

        occupation_text = ""
        if job.get("occupation_code"):
            confidence_pct = int((job.get("occupation_confidence", 0) * 100))
            occupation_text = f"\nJob Classification: {job['occupation_code']} ({confidence_pct}% confidence match)"

        salary_source_text = ""
        if job.get("salary_source"):
            salary_reliability = "Estimated by Glassdoor" if job["salary_source"] == "ESTIMATED" else "Provided by Employer"
            salary_source_text = f"\nSalary Data Source: {salary_reliability}"

        sponsored_text = ""
        if job.get("is_sponsored"):
            level = job.get("sponsorship_level", "Sponsored")
            sponsored_text = f"\n⚠️ This is a {level} job posting"

        company_text = f"""Company: {job_sections.company.company_name}
Size: {job_sections.company.company_size or "Not specified"} ({job_sections.company.get_size_category()})
Revenue: {job_sections.company.company_revenue or "Not specified"}
Website: {job_sections.company.company_website or "Not available"}{company_rating_text}{easy_apply_text}{occupation_text}{salary_source_text}{sponsored_text}

About the Company:
{company_description}"""

        # === DESCRIPTION ===
        description = job.get("description", "No description available")

        resume_text = self.analyzer.resume_text or "No resume provided"
        candidate_requirements_text = self.analyzer.get_requirements_text()
        preferences_text = self.analyzer.get_preferences_text()

        prompt = f"""You are an expert job matching system. Evaluate how well this job posting matches what the candidate is looking for AND whether they're qualified.

**JOB POSTING:**

**TITLE & ROLE:**
{title_text}

**REQUIREMENTS:**
{requirements_text}

**COMPENSATION & BENEFITS:**
{compensation_text}

**WORK ARRANGEMENTS:**
{work_text}

**COMPANY:**
{company_text}

**FULL JOB DESCRIPTION:**
{description}

---

**CANDIDATE RESUME:**
{resume_text}

---

**CANDIDATE'S REQUIREMENTS AND PREFERENCES:**

{candidate_requirements_text}

**ADDITIONAL PREFERENCES (salary/location from filters):**
{preferences_text}

---

**EVALUATION INSTRUCTIONS:**

Complete each evaluation step and track your assessment. Your final score MUST reflect the cumulative result of all steps.

**STEP 1: DEAL-BREAKER CHECK**
Review ONLY the MUST-HAVES and AVOID lists (these are the ONLY deal-breakers):
- Does this job satisfy ALL MUST-HAVES? (Yes/No)
- Does this job contain ANY AVOID items? (Yes/No)
- If ANY deal-breaker is triggered → Cap score at 49 maximum

IMPORTANT: Skills and other preferences are NOT deal-breakers. A job missing some preferred skills should NOT be disqualified. Only MUST-HAVES and AVOID items can disqualify a job.

**STEP 2: DOMAIN MATCH CHECK**
Read the ENTIRE job description to determine the actual role:
- What is the primary domain? (e.g., data engineering, frontend, DevOps, etc.)
- Does this match the candidate's target domain? (Yes/Partial/No)
- If NO (wrong domain entirely) → Cap score at 59 maximum
- If PARTIAL (adjacent/overlapping domain) → Cap score at 74 maximum

**STEP 3: ROLE ALIGNMENT SCORING** (0-30 points)
How well does the role match what the candidate wants?
- 25-30: Exact target role match (title AND responsibilities align perfectly)
- 18-24: Strong alignment (clearly in target domain, minor title/scope differences)
- 10-17: Moderate alignment (right domain but different focus area)
- 0-9: Weak alignment (tangentially related)

**STEP 4: QUALIFICATIONS FIT SCORING** (0-40 points)
How qualified is the candidate for this specific role?
- 35-40: Exceeds requirements (candidate has more experience/skills than the job requires)
- 28-34: Fully qualified (candidate meets all key requirements listed in the job)
- 20-27: Mostly qualified (candidate meets most requirements, missing 1-2 specific skills)
- 12-19: Partially qualified (candidate is missing several required skills or significant experience)
- 0-11: Under-qualified (candidate lacks fundamental skills or experience for this role)

**STEP 5: PREFERENCES SCORING** (0-30 points)
How well does the job meet the candidate's stated preferences?
- Remote/location preference met? (0-10 points)
- Salary in acceptable range? (0-10 points)
- Other preferences (company size, tech stack, etc.)? (0-10 points)

**WHAT MATTERS VS. WHAT DOESN'T:**

Things that SHOULD impact the score:
- Does the job match the candidate's target role and domain?
- Does the candidate have the technical skills the job requires?
- Does the job meet the candidate's must-haves (remote, salary, etc.)?
- Does the job trigger any avoid items?

Things that should NOT significantly impact the score:
- Lack of experience at the specific company (everyone is new to a company when they join)
- Lack of experience in the specific industry/vertical (transferable skills matter more)
- Candidate having MORE skills than the job mentions (this is a positive, not a gap)
- Unclear seniority levels or job leveling systems
- Minor differences in job title wording (e.g., "Data Platform Engineer" vs "Data Engineer")
- Job not using ALL of the candidate's listed skills (the candidate's skills are a POOL of technologies they know - a job only needs to match SOME of them, not all)

**FINAL SCORE CALCULATION:**
1. Sum your points from Steps 3-5 (maximum 100)
2. Apply any caps from Steps 1-2 if triggered
3. The result is your match_score

**SCORE INTERPRETATION:**
- 85-100: Strong match - Right role, candidate can do the job, core preferences met. May still have minor gaps.
- 70-84: Good match - Right domain, candidate is qualified, some preference trade-offs. May have a few gaps.
- 50-69: Moderate match - Alignment concerns (adjacent role, missing important skills, or significant preference gaps)
- 0-49: Poor match - Wrong domain, deal-breaker triggered, or candidate lacks core required skills

Note: Having gaps does NOT mean the score should be low. Most real job matches have some gaps - what matters is whether the candidate can do the job and the job meets their core requirements.

**REASONING REQUIREMENTS:**
In your 2-3 sentence explanation, state:
1. The actual role type and whether it matches the target domain
2. Key qualification matches or gaps
3. Any deal-breakers or preference issues

**CRITICAL OUTPUT REQUIREMENTS:**
- You MUST respond with ONLY a JSON object
- DO NOT include any explanations, thinking, or text before or after the JSON
- DO NOT use markdown code blocks or formatting
- The response must start with {{ and end with }}

**REQUIRED JSON FORMAT:**
{{
  "match_score": <integer from 0 to 100>,
  "reasoning": "<2-3 sentences: role type + domain match, qualification fit, any concerns>",
  "matched_requirements": {{}}
}}"""

        return prompt

    def score_jobs_batch(
        self, jobs: list, progress_callback: Optional[callable] = None, apply_pre_filters: bool = True
    ) -> list:
        """
        Score multiple jobs (with multi-threading support and pre-filtering)

        Args:
            jobs: List of job dicts
            progress_callback: Optional callback function(current, total, job)
            apply_pre_filters: If True, applies deterministic filters before AI scoring (default: True)

        Returns:
            List of jobs with added match_score, reasoning, etc.
        """
        # Reset tracking lists
        self.failed_jobs = []
        self.rejected_jobs = []
        self.filtered_jobs = []

        # Get thread count from environment
        max_workers = int(os.getenv("MATCH_THREADS", "4"))
        total = len(jobs)

        # Get list of already-processed jobs from checkpoint
        processed_urls = set()
        if self.checkpoint_manager:
            processed_urls = set(self.checkpoint_manager.get_processed_urls("scoring"))

        # Filter out already-processed jobs
        jobs_to_process = [job for job in jobs if job.get("job_url", "") not in processed_urls]

        if not jobs_to_process:
            return []

        # APPLY DETERMINISTIC PRE-FILTERS
        if apply_pre_filters:
            print(f"\n🔍 Applying deterministic filters to {len(jobs_to_process)} jobs...")

            passed_jobs, rejected_jobs, filter_stats = apply_filters_to_jobs(
                jobs_to_process,
                self.analyzer.candidate_profile,
                self.analyzer.preferences
            )

            # Track filtered jobs
            self.filtered_jobs = rejected_jobs

            # Print filter statistics
            print(f"✅ Filters passed: {filter_stats['passed_jobs']} jobs")
            print(f"❌ Filters rejected: {filter_stats['rejected_jobs']} jobs")
            print(f"📊 Pass rate: {filter_stats['pass_rate']*100:.1f}%")

            if filter_stats['rejection_reasons']:
                print(f"\n📋 Rejection breakdown:")
                for reason, count in filter_stats['rejection_reasons'].items():
                    print(f"   • {reason}: {count} jobs")

            # Use filtered jobs for AI scoring
            jobs_to_process = passed_jobs
        else:
            # TITLE RELEVANCE FILTER (legacy fallback if pre-filters disabled)
            relevant_jobs = []
            for job in jobs_to_process:
                if self._is_title_relevant(job):
                    relevant_jobs.append(job)
                else:
                    self.rejected_jobs.append(job)

            jobs_to_process = relevant_jobs

        if not jobs_to_process:
            print("\n[WARNING] No jobs passed filters!")
            return []

        # Update total to reflect filtered count
        total = len(jobs_to_process)

        print(f"\n[INFO] Scoring {len(jobs_to_process)} jobs with AI...\n")

        # Thread-safe progress tracking and failure tracking
        progress_lock = threading.Lock()
        completed_count = [0]  # Use list for mutable reference

        def process_single_job(job):
            """Process a single job and update progress"""
            job_url = job.get("job_url", "")

            try:
                # Score the job
                score_result = self.score_job(job)

                if score_result:
                    # Add scoring results to job
                    job_with_score = {**job, **score_result}
                else:
                    # Job failed to score, add with 0 score
                    job_with_score = {
                        **job,
                        "match_score": 0,
                        "reasoning": "Failed to score job",
                        "matched_requirements": {},
                        "preference_checks": {},
                    }
                    # Track failure (thread-safe)
                    with progress_lock:
                        self.failed_jobs.append(job)

                # Save checkpoint after each job (thread-safe)
                if self.checkpoint_manager and job_url:
                    self.checkpoint_manager.mark_job_completed("scoring", job_url)

                # Update progress (thread-safe)
                with progress_lock:
                    completed_count[0] += 1
                    if progress_callback:
                        progress_callback(completed_count[0], total, job)

                return job_with_score

            except Exception as e:
                print(f"[WARNING] Error processing job {job.get('title', 'Unknown')}: {e}")

                # Record failure
                error_msg = f"Thread execution error: {str(e)}"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "scoring", ErrorType.UNKNOWN_ERROR, error_msg)

                # Track failure
                with progress_lock:
                    self.failed_jobs.append(job)

                # Return job with error state
                return {
                    **job,
                    "match_score": 0,
                    "reasoning": f"Error during processing: {str(e)}",
                    "matched_requirements": {},
                    "preference_checks": {},
                }

        # Process jobs using smooth batch processor (maintains constant GPU load)
        processor = SmoothBatchProcessor(max_workers=max_workers)
        scored_jobs = processor.process_batch(jobs_to_process, process_single_job)

        return scored_jobs

    def score_jobs_batch_queued(
        self, jobs: list, progress_callback: Optional[callable] = None, apply_pre_filters: bool = True
    ) -> list:
        """
        Score multiple jobs using batch queue processing (constant GPU load)

        This method pre-generates all prompts and queues AI requests continuously
        to maintain constant GPU utilization, eliminating power spikes.

        Args:
            jobs: List of job dicts
            progress_callback: Optional callback function(current, total, job)
            apply_pre_filters: If True, applies deterministic filters before AI scoring (default: True)

        Returns:
            List of jobs with added match_score, reasoning, etc.
        """
        import time
        from .batch_queue_processor import BatchQueueProcessor

        # Reset tracking lists
        self.failed_jobs = []
        self.rejected_jobs = []
        self.filtered_jobs = []

        # Get configuration
        max_workers = int(os.getenv("MATCH_THREADS", "4"))
        queue_delay_ms = int(os.getenv("BATCH_QUEUE_DELAY_MS", "50"))

        # Filter out already-processed jobs from checkpoint
        jobs_to_process = jobs
        if self.checkpoint_manager:
            processed_urls = set(self.checkpoint_manager.get_processed_urls("scoring"))
            jobs_to_process = [job for job in jobs if job.get("job_url", "") not in processed_urls]

        if not jobs_to_process:
            return []

        # APPLY DETERMINISTIC PRE-FILTERS
        if apply_pre_filters:
            print(f"\n🔍 Applying deterministic filters to {len(jobs_to_process)} jobs...")

            passed_jobs, rejected_jobs, filter_stats = apply_filters_to_jobs(
                jobs_to_process,
                self.analyzer.candidate_profile,
                self.analyzer.preferences
            )

            # Track filtered jobs
            self.filtered_jobs = rejected_jobs

            # Print filter statistics
            print(f"✅ Filters passed: {filter_stats['passed_jobs']} jobs")
            print(f"❌ Filters rejected: {filter_stats['rejected_jobs']} jobs")
            print(f"📊 Pass rate: {filter_stats['pass_rate']*100:.1f}%")

            if filter_stats['rejection_reasons']:
                print(f"\n📋 Rejection breakdown:")
                for reason, count in filter_stats['rejection_reasons'].items():
                    print(f"   • {reason}: {count} jobs")

            # Use filtered jobs for AI scoring
            jobs_to_process = passed_jobs
        else:
            # TITLE RELEVANCE FILTER (legacy fallback if pre-filters disabled)
            relevant_jobs = []
            for job in jobs_to_process:
                if self._is_title_relevant(job):
                    relevant_jobs.append(job)
                else:
                    self.rejected_jobs.append(job)

            jobs_to_process = relevant_jobs

        if not jobs_to_process:
            print("\n[WARNING] No jobs passed filters!")
            return []

        print(f"\n[INFO] Scoring {len(jobs_to_process)} jobs with AI (batch queue mode)...\n")

        # PHASE 0: PRE-COMPUTE ALL DETERMINISTIC SCORES (CPU phase before GPU)
        print(f"[INFO] Computing deterministic scores for {len(jobs_to_process)} jobs...")
        phase_start = time.time()

        deterministic_scores_map = {}
        for job in jobs_to_process:
            job_url = job.get("job_url", "")
            try:
                deterministic_scores_map[job_url] = self.comparison_engine.calculate_deterministic_score(job)
            except Exception as e:
                print(f"[WARNING] Deterministic scoring failed for {job.get('title', 'Unknown')}: {e}")
                deterministic_scores_map[job_url] = None

        print(f"[INFO] Deterministic scoring: {time.time() - phase_start:.2f}s")

        # Define prompt generator (now uses pre-computed scores)
        def prompt_generator(job: Dict[str, Any]) -> str:
            """Generate scoring prompt for a job"""
            # Use pre-computed deterministic score (NO calculation here!)
            job_url = job.get("job_url", "")
            job['_deterministic_scores'] = deterministic_scores_map.get(job_url)
            return self._create_scoring_prompt(job)

        # Define AI parameters for async batch mode
        json_schema = {
            "type": "object",
            "properties": {
                "match_score": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Match score from 0 to 100"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of the score (2-3 sentences)"
                },
                "matched_requirements": {
                    "type": "object",
                    "description": "Dictionary of matched requirements (can be empty)"
                }
            },
            "required": ["match_score", "reasoning", "matched_requirements"]
        }

        # Define AI executor (fallback for thread-based mode)
        def ai_executor(prompt: str) -> Optional[Dict[str, Any]]:
            """Execute AI request for scoring (fallback if async batch not available)"""
            try:
                response = self.client.generate_json(
                    prompt,
                    temperature=0.2,
                    max_tokens=2048,
                    json_schema=json_schema
                )
                return response
            except Exception as e:
                return None

        # Define result merger
        def result_merger(job: Dict[str, Any], result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
            """Merge AI result into job dict"""
            # Get deterministic scores from temporary storage
            deterministic_scores = job.pop('_deterministic_scores', None)

            if result and isinstance(result, dict):
                # Extract AI score and reasoning
                ai_match_score = result.get("match_score", 0)
                ai_reasoning = result.get("reasoning", "No reasoning provided")
                matched_requirements = result.get("matched_requirements", {})

                # Validate AI score
                if not isinstance(ai_match_score, (int, float)) or ai_match_score < 0 or ai_match_score > 100:
                    ai_match_score = 0

                # Combine with deterministic scores if available
                if deterministic_scores:
                    combined = self.comparison_engine.combine_scores(
                        deterministic_scores,
                        int(ai_match_score),
                        ai_reasoning
                    )
                    final_score = int(combined['combined_score'])
                    final_reasoning = f"[Hybrid Score: {final_score}/100 = Deterministic {combined['deterministic_component']:.0f} + AI {combined['ai_component']:.0f}]\n\n{ai_reasoning}"

                    scoring_breakdown = {
                        "deterministic_score": deterministic_scores['deterministic_score'],
                        "ai_score": int(ai_match_score),
                        "combined_score": final_score,
                        "deterministic_breakdown": deterministic_scores,
                    }
                else:
                    final_score = int(ai_match_score)
                    final_reasoning = ai_reasoning
                    scoring_breakdown = None

                # Check preferences
                preference_checks = self.analyzer.validate_job_preferences(job)

                # Build result
                job_with_score = {
                    **job,
                    "match_score": final_score,
                    "reasoning": final_reasoning,
                    "matched_requirements": matched_requirements,
                    "preference_checks": preference_checks,
                }

                if scoring_breakdown:
                    job_with_score["scoring_breakdown"] = scoring_breakdown

                return job_with_score
            else:
                # Failure case
                self.failed_jobs.append(job)
                return {
                    **job,
                    "match_score": 0,
                    "reasoning": "Failed to score job",
                    "matched_requirements": {},
                    "preference_checks": {},
                }

        # Create batch queue processor
        processor = BatchQueueProcessor(
            max_workers=max_workers,
            queue_delay_ms=queue_delay_ms
        )

        # Process batch with async batch mode enabled
        scored_jobs = processor.process_batch(
            jobs=jobs_to_process,
            prompt_generator=prompt_generator,
            ai_executor=ai_executor,
            result_merger=result_merger,
            progress_callback=progress_callback,
            checkpoint_manager=self.checkpoint_manager,
            checkpoint_stage="scoring",
            failure_tracker=self.failure_tracker,
            failure_stage="scoring",
            llama_client=self.client,  # Pass LlamaClient for async batch mode
            temperature=0.2,  # AI generation temperature
            max_tokens=2048,  # Max tokens for AI generation
            json_schema=json_schema,  # JSON schema for validation
        )

        return scored_jobs

    def get_failed_jobs(self) -> List[Dict[str, Any]]:
        """
        Get list of jobs that failed during the last batch scoring

        Returns:
            List of failed job dicts
        """
        return self.failed_jobs

    def get_rejected_jobs(self) -> List[Dict[str, Any]]:
        """
        Get list of jobs rejected by title filter

        Returns:
            List of rejected job dicts
        """
        return self.rejected_jobs

    def get_filtered_jobs(self) -> List[Dict[str, Any]]:
        """
        Get list of jobs rejected by deterministic filters

        Returns:
            List of filtered job dicts with rejection reasons
        """
        return self.filtered_jobs

    def filter_by_score(
        self, jobs: list, min_score: int = 60
    ) -> tuple[list, list]:
        """
        Filter jobs by minimum match score

        Args:
            jobs: List of scored jobs
            min_score: Minimum score threshold

        Returns:
            Tuple of (matched_jobs, rejected_jobs)
        """
        matched = [job for job in jobs if job.get("match_score", 0) >= min_score]
        rejected = [job for job in jobs if job.get("match_score", 0) < min_score]

        return matched, rejected


if __name__ == "__main__":
    # Test the scorer
    print("Testing MatchScorer...")

    from dotenv import load_dotenv

    load_dotenv()

    # Initialize components
    client = LlamaClient()
    analyzer = ResumeAnalyzer()

    print("Loading resume and requirements...")
    try:
        analyzer.load_all()
        print("Loaded successfully")
    except Exception as e:
        print(f"X Error loading: {e}")
        exit(1)

    # Create scorer
    scorer = MatchScorer(client, analyzer)

    # Test with a sample job
    sample_job = {
        "title": "Senior Payroll Manager",
        "company": "Test Company",
        "location": "Remote",
        "job_type": "full-time",
        "remote": True,
        "salary_min": 80000,
        "salary_max": 120000,
        "salary_currency": "USD",
        "salary_period": "yearly",
        "description": """
We are seeking an experienced Senior Payroll Manager to oversee our multi-state payroll operations.

Requirements:
- 5+ years payroll management experience
- Strong knowledge of ADP and Workday
- Multi-state payroll compliance expertise
- Bachelor's degree in Accounting or Finance
- Advanced Excel skills
- Strong attention to detail
        """,
    }

    print("\nScoring sample job...")
    result = scorer.score_job(sample_job)

    if result:
        print(f"\nMatch Score: {result['match_score']}/100")
        print(f"Reasoning: {result['reasoning']}")
        print(f"\nMatched Requirements:")
        for req, matched in result["matched_requirements"].items():
            status = "✅" if matched else "X"
            print(f"  {status} {req}")
    else:
        print("X Scoring failed")

    print("\nMatchScorer test complete")
