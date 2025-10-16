"""
GapAnalyzer - Pass 2: Detailed Gap Analysis

Provides detailed analysis of job matches, identifying strengths, gaps,
and overall fit assessment.
Supports multi-threaded processing for faster batch analysis.
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
from .models.job_sections import extract_job_sections
from .comparison_engine import ComparisonEngine
from .smooth_batch_processor import SmoothBatchProcessor


class GapAnalyzer:
    """Analyze gaps between job requirements and candidate qualifications"""

    def __init__(
        self, llama_client: LlamaClient, resume_analyzer: ResumeAnalyzer,
        checkpoint_manager=None, failure_tracker: Optional[FailureTracker] = None
    ):
        """
        Initialize GapAnalyzer

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

        # Initialize comparison engine for section-based analysis
        self.comparison_engine = ComparisonEngine(
            self.analyzer.candidate_profile,
            self.analyzer.preferences
        )

    def analyze_job(self, job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Perform detailed gap analysis on a job

        Args:
            job: Job dict with match_score and other fields from Pass 1

        Returns:
            Dict with strengths, gaps, red_flags, and assessment
            Returns None if analysis fails
        """
        try:
            prompt = self._create_analysis_prompt(job)

            # Generate response
            try:
                response = self.client.generate_json(prompt, temperature=0.4, max_tokens=2048)
            except requests.exceptions.Timeout:
                error_msg = "Request timed out"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "analysis", ErrorType.TIMEOUT_ERROR, error_msg)
                print(f"[WARNING] Timeout analyzing job: {job.get('title', 'Unknown')}")
                return None
            except requests.exceptions.ConnectionError as e:
                error_msg = f"Connection error: {str(e)}"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "analysis", ErrorType.CONNECTION_ERROR, error_msg)
                print(f"[WARNING] Connection error analyzing job: {job.get('title', 'Unknown')}")
                return None
            except json.JSONDecodeError as e:
                error_msg = f"JSON parse error: {str(e)}"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "analysis", ErrorType.JSON_PARSE_ERROR, error_msg)
                print(f"[WARNING] JSON parse error analyzing job: {job.get('title', 'Unknown')}")
                return None

            if not response:
                error_msg = "Empty response from AI"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "analysis", ErrorType.UNKNOWN_ERROR, error_msg)
                print(f"[WARNING] Failed to analyze job: {job.get('title', 'Unknown')}")
                return None

            # Validate required fields
            required_fields = ["strengths", "gaps", "red_flags", "assessment"]
            missing_fields = [f for f in required_fields if f not in response]
            if missing_fields:
                error_msg = f"Missing required fields: {', '.join(missing_fields)}"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "analysis", ErrorType.VALIDATION_ERROR, error_msg)
                print(f"[WARNING] Validation error analyzing job: {error_msg}")
                return None

            return {
                "strengths": response.get("strengths", []),
                "gaps": response.get("gaps", []),
                "red_flags": response.get("red_flags", []),
                "assessment": response.get("assessment", "No assessment provided"),
            }

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            if self.failure_tracker:
                self.failure_tracker.record_failure(job, "analysis", ErrorType.UNKNOWN_ERROR, error_msg)
            print(f"[WARNING] Unexpected error analyzing job {job.get('title', 'Unknown')}: {e}")
            return None

    def _create_analysis_prompt(self, job: Dict[str, Any]) -> str:
        """
        Create AI prompt for section-based gap analysis

        Args:
            job: Job dict with scoring results

        Returns:
            Formatted prompt string
        """
        # Extract structured job sections
        job_sections = extract_job_sections(job)

        # Get section comparison
        section_comparison = self.comparison_engine.get_section_comparison(job)

        match_score = job.get("match_score", 0)
        reasoning = job.get("reasoning", "No reasoning provided")

        # Build structured job sections text (similar to match_scorer)
        title_text = f"""Title: {job_sections.title.job_title}
Seniority: {job_sections.title.seniority_level}
Family: {job_sections.title.job_family}"""

        skills_text = ", ".join(job_sections.requirements.skills) if job_sections.requirements.skills else "Not specified"
        requirements_text = ", ".join(job_sections.requirements.requirements) if job_sections.requirements.requirements else "Not specified"

        salary_text = "Not specified"
        if job_sections.compensation.salary_min and job_sections.compensation.salary_max:
            salary_text = f"${job_sections.compensation.salary_min:,.0f} - ${job_sections.compensation.salary_max:,.0f}"

        benefits_text = ", ".join(job_sections.compensation.benefits) if job_sections.compensation.benefits else "Not specified"

        description = job.get("description", "No description available")
        resume_text = self.analyzer.resume_text or "No resume provided"
        profile_text = self.analyzer.get_requirements_text()

        prompt = f"""CRITICAL: YOU MUST RESPOND WITH ONLY JSON. NO THINKING. NO EXPLANATION. NO TEXT BEFORE OR AFTER THE JSON. START YOUR RESPONSE WITH THE OPENING BRACE {{

You are an expert career advisor. You previously scored this job at {match_score}/100 with the following reasoning: "{reasoning}"

Now provide a detailed section-by-section gap analysis to help the candidate understand their fit for this position.

**JOB POSTING:**

**TITLE & ROLE:**
{title_text}

**REQUIREMENTS:**
Skills: {skills_text}
Requirements: {requirements_text}

**COMPENSATION:**
Salary: {salary_text}
Benefits: {benefits_text}

**WORK ARRANGEMENTS:**
Remote: {"Yes" if job_sections.work.remote else "No"}
Location: {job_sections.work.location}

**COMPANY:**
{job_sections.company.company_name}
Size: {job_sections.company.company_size or "Not specified"}

**FULL DESCRIPTION:**
{description}

---

**CANDIDATE RESUME:**
{resume_text}

---

**{profile_text}**

---

**PREVIOUS SCORING:**
Match Score: {match_score}/100
Reasoning: {reasoning}

---

**INSTRUCTIONS:**
Provide a comprehensive section-by-section analysis:

1. **Strengths**: List 3-5 specific reasons why this candidate is a good fit. For each strength:
   - Reference actual experience from their resume
   - Connect it to specific job requirements or sections
   - Focus on title match, skills alignment, experience level fit

2. **Gaps**: List specific skills, experience, or qualifications the candidate lacks. Organize by section:
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
   - How well each major section aligns (title, requirements, compensation, work arrangements)
   - Whether this advances their career goals

**CRITICAL OUTPUT REQUIREMENTS:**
- YOU MUST RESPOND WITH ONLY JSON
- DO NOT WRITE ANY TEXT, THINKING, OR EXPLANATION BEFORE THE JSON
- DO NOT USE MARKDOWN
- START YOUR RESPONSE WITH THE OPENING BRACE {{
- END YOUR RESPONSE WITH THE CLOSING BRACE }}
- THE FIRST CHARACTER OF YOUR RESPONSE MUST BE {{

**REQUIRED JSON FORMAT:**
{{
  "strengths": [
    "Specific strength with evidence from resume",
    "Another strength with evidence",
    ...
  ],
  "gaps": [
    "Specific missing skill or experience",
    "Another gap",
    ...
  ],
  "red_flags": [
    "Serious concern if any",
    ...
  ],
  "assessment": "Overall 2-3 sentence recommendation"
}}

Be specific and reference actual details from the resume, candidate profile, and job description."""

        return prompt

    def analyze_jobs_batch(
        self, jobs: list, progress_callback: Optional[callable] = None
    ) -> list:
        """
        Analyze multiple jobs (with multi-threading support)

        Args:
            jobs: List of job dicts (should already have match scores)
            progress_callback: Optional callback function(current, total, job)

        Returns:
            List of jobs with added analysis fields
        """
        # Reset failed jobs list
        self.failed_jobs = []

        # Get thread count from environment
        max_workers = int(os.getenv("MATCH_THREADS", "4"))
        total = len(jobs)

        # Get list of already-processed jobs from checkpoint
        processed_urls = set()
        if self.checkpoint_manager:
            processed_urls = set(self.checkpoint_manager.get_processed_urls("analysis"))

        # Filter out already-processed jobs
        jobs_to_process = [job for job in jobs if job.get("job_url", "") not in processed_urls]

        if not jobs_to_process:
            return []

        # Thread-safe progress tracking and failure tracking
        progress_lock = threading.Lock()
        completed_count = [0]  # Use list for mutable reference

        def process_single_job(job):
            """Process a single job and update progress"""
            job_url = job.get("job_url", "")

            try:
                # Analyze the job
                analysis_result = self.analyze_job(job)

                if analysis_result:
                    # Add analysis results to job
                    job_with_analysis = {**job, **analysis_result}
                else:
                    # Job failed to analyze, add with empty fields
                    job_with_analysis = {
                        **job,
                        "strengths": [],
                        "gaps": [],
                        "red_flags": [],
                        "assessment": "Failed to analyze job",
                    }
                    # Track failure (thread-safe)
                    with progress_lock:
                        self.failed_jobs.append(job)

                # Save checkpoint after each job (thread-safe)
                if self.checkpoint_manager and job_url:
                    self.checkpoint_manager.mark_job_completed("analysis", job_url)

                # Update progress (thread-safe)
                with progress_lock:
                    completed_count[0] += 1
                    if progress_callback:
                        progress_callback(completed_count[0], total, job)

                return job_with_analysis

            except Exception as e:
                print(f"[WARNING] Error analyzing job {job.get('title', 'Unknown')}: {e}")

                # Record failure
                error_msg = f"Thread execution error: {str(e)}"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "analysis", ErrorType.UNKNOWN_ERROR, error_msg)

                # Track failure
                with progress_lock:
                    self.failed_jobs.append(job)

                # Return job with error state
                return {
                    **job,
                    "strengths": [],
                    "gaps": [],
                    "red_flags": [],
                    "assessment": f"Error during analysis: {str(e)}",
                }

        # Process jobs using smooth batch processor (maintains constant GPU load)
        processor = SmoothBatchProcessor(max_workers=max_workers)
        analyzed_jobs = processor.process_batch(jobs_to_process, process_single_job)

        return analyzed_jobs

    def analyze_jobs_batch_queued(
        self, jobs: list, progress_callback: Optional[callable] = None
    ) -> list:
        """
        Analyze multiple jobs using batch queue processing (constant GPU load)

        This method pre-generates all prompts and queues AI requests continuously
        to maintain constant GPU utilization, eliminating power spikes.

        Args:
            jobs: List of job dicts (should already have match scores)
            progress_callback: Optional callback function(current, total, job)

        Returns:
            List of jobs with added analysis fields
        """
        from .batch_queue_processor import BatchQueueProcessor

        # Reset failed jobs list
        self.failed_jobs = []

        # Get configuration
        max_workers = int(os.getenv("MATCH_THREADS", "4"))
        queue_delay_ms = int(os.getenv("BATCH_QUEUE_DELAY_MS", "50"))

        # Filter out already-processed jobs from checkpoint
        jobs_to_process = jobs
        if self.checkpoint_manager:
            processed_urls = set(self.checkpoint_manager.get_processed_urls("analysis"))
            jobs_to_process = [job for job in jobs if job.get("job_url", "") not in processed_urls]

        if not jobs_to_process:
            return []

        print(f"\n[INFO] Analyzing {len(jobs_to_process)} jobs (batch queue mode)...\n")

        # Define prompt generator
        def prompt_generator(job: Dict[str, Any]) -> str:
            """Generate analysis prompt for a job"""
            return self._create_analysis_prompt(job)

        # Define AI executor
        def ai_executor(prompt: str) -> Optional[Dict[str, Any]]:
            """Execute AI request for analysis"""
            try:
                response = self.client.generate_json(prompt, temperature=0.4, max_tokens=2048)
                return response
            except Exception:
                return None

        # Define result merger
        def result_merger(job: Dict[str, Any], result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
            """Merge AI result into job dict"""
            if result and isinstance(result, dict):
                # Validate required fields
                required_fields = ["strengths", "gaps", "red_flags", "assessment"]
                if all(field in result for field in required_fields):
                    return {
                        **job,
                        "strengths": result.get("strengths", []),
                        "gaps": result.get("gaps", []),
                        "red_flags": result.get("red_flags", []),
                        "assessment": result.get("assessment", "No assessment provided"),
                    }

            # Failure case
            self.failed_jobs.append(job)
            return {
                **job,
                "strengths": [],
                "gaps": [],
                "red_flags": [],
                "assessment": "Failed to analyze job",
            }

        # Define JSON schema for gap analysis
        json_schema = {
            "type": "object",
            "properties": {
                "strengths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of candidate strengths for this role"
                },
                "gaps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of skills or experience gaps"
                },
                "red_flags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of serious concerns or deal-breakers"
                },
                "assessment": {
                    "type": "string",
                    "description": "Overall 2-3 sentence assessment"
                }
            },
            "required": ["strengths", "gaps", "red_flags", "assessment"]
        }

        # Create batch queue processor
        processor = BatchQueueProcessor(
            max_workers=max_workers,
            queue_delay_ms=queue_delay_ms
        )

        # Process batch with async batch mode enabled
        analyzed_jobs = processor.process_batch(
            jobs=jobs_to_process,
            prompt_generator=prompt_generator,
            ai_executor=ai_executor,
            result_merger=result_merger,
            progress_callback=progress_callback,
            checkpoint_manager=self.checkpoint_manager,
            checkpoint_stage="analysis",
            failure_tracker=self.failure_tracker,
            failure_stage="analysis",
            llama_client=self.client,  # Pass LlamaClient for async batch mode
            temperature=0.4,  # AI generation temperature (slightly higher for creative analysis)
            max_tokens=2048,  # Max tokens for AI generation (more for detailed analysis)
            json_schema=json_schema,  # JSON schema for validation
        )

        return analyzed_jobs

    def get_failed_jobs(self) -> List[Dict[str, Any]]:
        """
        Get list of jobs that failed during the last batch analysis

        Returns:
            List of failed job dicts
        """
        return self.failed_jobs

    def get_summary_stats(self, jobs: list) -> Dict[str, Any]:
        """
        Get summary statistics from analyzed jobs

        Args:
            jobs: List of analyzed jobs

        Returns:
            Dict with summary statistics
        """
        if not jobs:
            return {
                "total_jobs": 0,
                "avg_strengths": 0,
                "avg_gaps": 0,
                "jobs_with_red_flags": 0,
            }

        total_strengths = sum(len(job.get("strengths", [])) for job in jobs)
        total_gaps = sum(len(job.get("gaps", [])) for job in jobs)
        jobs_with_flags = sum(1 for job in jobs if job.get("red_flags", []))

        return {
            "total_jobs": len(jobs),
            "avg_strengths": round(total_strengths / len(jobs), 1),
            "avg_gaps": round(total_gaps / len(jobs), 1),
            "jobs_with_red_flags": jobs_with_flags,
        }


if __name__ == "__main__":
    # Test the analyzer
    print("Testing GapAnalyzer...")

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

    # Create gap analyzer
    gap_analyzer = GapAnalyzer(client, analyzer)

    # Test with a sample scored job
    sample_job = {
        "title": "Senior Payroll Manager",
        "company": "Test Company",
        "location": "Remote",
        "description": """
We are seeking an experienced Senior Payroll Manager to oversee our multi-state payroll operations.

Requirements:
- 5+ years payroll management experience
- Strong knowledge of ADP and Workday
- Multi-state payroll compliance expertise
- Bachelor's degree in Accounting or Finance
- Advanced Excel skills
        """,
        "match_score": 75,
        "reasoning": "Candidate has strong payroll experience but lacks Workday expertise",
        "matched_requirements": {
            "Payroll processing experience": True,
            "Multi-state compliance": True,
            "Bachelor's degree": True,
            "Workday HCM experience": False,
        },
    }

    print("\nAnalyzing sample job...")
    result = gap_analyzer.analyze_job(sample_job)

    if result:
        print("\nGap Analysis Complete")
        print("\nStrengths:")
        for strength in result["strengths"]:
            print(f"  {strength}")

        print("\nGaps:")
        for gap in result["gaps"]:
            print(f"  [WARNING] {gap}")

        if result["red_flags"]:
            print("\nRed Flags:")
            for flag in result["red_flags"]:
                print(f"  [WARNING] {flag}")

        print(f"\nAssessment: {result['assessment']}")
    else:
        print("X Analysis failed")

    print("\nGapAnalyzer test complete")
