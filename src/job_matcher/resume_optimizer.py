"""
ResumeOptimizer - Pass 3: Resume Recommendations

Provides tailored resume optimization recommendations for each job,
including keywords, experience highlights, and cover letter talking points.
Supports multi-threaded processing for faster batch optimization.
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
from .smooth_batch_processor import SmoothBatchProcessor


class ResumeOptimizer:
    """Generate resume optimization recommendations for job matches"""

    def __init__(
        self, llama_client: LlamaClient, resume_analyzer: ResumeAnalyzer,
        checkpoint_manager=None, failure_tracker: Optional[FailureTracker] = None
    ):
        """
        Initialize ResumeOptimizer

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

    def optimize_for_job(self, job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate resume optimization recommendations for a job

        Args:
            job: Job dict with match_score, analysis, etc. from previous passes

        Returns:
            Dict with keywords, highlights, sections_to_expand, and cover_letter_points
            Returns None if optimization fails
        """
        try:
            prompt = self._create_optimization_prompt(job)

            # Generate response
            try:
                response = self.client.generate_json(prompt, temperature=0.5, max_tokens=2048)
            except requests.exceptions.Timeout:
                error_msg = "Request timed out"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "optimization", ErrorType.TIMEOUT_ERROR, error_msg)
                print(f"[WARNING] Timeout optimizing job: {job.get('title', 'Unknown')}")
                return None
            except requests.exceptions.ConnectionError as e:
                error_msg = f"Connection error: {str(e)}"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "optimization", ErrorType.CONNECTION_ERROR, error_msg)
                print(f"[WARNING] Connection error optimizing job: {job.get('title', 'Unknown')}")
                return None
            except json.JSONDecodeError as e:
                error_msg = f"JSON parse error: {str(e)}"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "optimization", ErrorType.JSON_PARSE_ERROR, error_msg)
                print(f"[WARNING] JSON parse error optimizing job: {job.get('title', 'Unknown')}")
                return None

            if not response:
                error_msg = "Empty response from AI"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "optimization", ErrorType.UNKNOWN_ERROR, error_msg)
                print(f"[WARNING] Failed to optimize for job: {job.get('title', 'Unknown')}")
                return None

            # Validate required fields
            required_fields = ["keywords", "experience_highlights", "sections_to_expand", "cover_letter_points", "resume_summary"]
            missing_fields = [f for f in required_fields if f not in response]
            if missing_fields:
                error_msg = f"Missing required fields: {', '.join(missing_fields)}"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "optimization", ErrorType.VALIDATION_ERROR, error_msg)
                print(f"[WARNING] Validation error optimizing job: {error_msg}")
                return None

            return {
                "keywords": response.get("keywords", []),
                "experience_highlights": response.get("experience_highlights", []),
                "sections_to_expand": response.get("sections_to_expand", []),
                "cover_letter_points": response.get("cover_letter_points", []),
                "resume_summary": response.get("resume_summary", ""),
            }

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            if self.failure_tracker:
                self.failure_tracker.record_failure(job, "optimization", ErrorType.UNKNOWN_ERROR, error_msg)
            print(f"[WARNING] Unexpected error optimizing job {job.get('title', 'Unknown')}: {e}")
            return None

    def _create_optimization_prompt(self, job: Dict[str, Any]) -> str:
        """
        Create AI prompt for resume optimization

        Args:
            job: Job dict with full analysis

        Returns:
            Formatted prompt string
        """
        job_title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        description = job.get("description", "No description available")
        match_score = job.get("match_score", 0)
        strengths = job.get("strengths", [])
        gaps = job.get("gaps", [])
        assessment = job.get("assessment", "")

        resume_text = self.analyzer.resume_text or "No resume provided"
        profile_text = self.analyzer.get_requirements_text()

        # Format strengths and gaps
        strengths_text = "\n".join([f"  {s}" for s in strengths])
        gaps_text = "\n".join([f"  [WARNING] {g}" for g in gaps])

        prompt = f"""CRITICAL: YOU MUST RESPOND WITH ONLY JSON. NO THINKING. NO EXPLANATION. NO TEXT BEFORE OR AFTER THE JSON. START YOUR RESPONSE WITH THE OPENING BRACE {{

You are an expert resume writer and career coach. You've analyzed this job posting and identified the candidate's strengths and gaps.

**JOB POSTING:**
Title: {job_title}
Company: {company}

Description:
{description}

---

**CANDIDATE RESUME:**
{resume_text}

---

**{profile_text}**

---

**MATCH ANALYSIS:**
Match Score: {match_score}/100

Strengths:
{strengths_text}

Gaps:
{gaps_text}

Assessment: {assessment}

---

**INSTRUCTIONS:**
Using the candidate's profile (their core strengths, technical skills, and career goals) along with their resume, provide specific, actionable recommendations to tailor this resume for this job application:

1. **Keywords**: List 5-10 important keywords from the job description that should appear in the resume. Focus on technical skills, tools, methodologies mentioned in the job posting.

2. **Experience Highlights**: List 3-5 specific bullets or achievements from the candidate's resume that should be FEATURED PROMINENTLY for this application. Include the actual text from their resume.

3. **Sections to Expand**: List 2-3 sections of the resume that should be expanded or emphasized, with specific guidance on what to add.

4. **Cover Letter Points**: List 3-4 key talking points for the cover letter that directly address the job requirements and highlight relevant experience.

5. **Resume Summary**: Write a 2-3 sentence professional summary statement tailored specifically for this job application. This should go at the top of the resume.

**CRITICAL OUTPUT REQUIREMENTS:**
- YOU MUST RESPOND WITH ONLY JSON
- DO NOT WRITE ANY TEXT, THINKING, OR EXPLANATION BEFORE THE JSON
- DO NOT USE MARKDOWN
- START YOUR RESPONSE WITH THE OPENING BRACE {{
- END YOUR RESPONSE WITH THE CLOSING BRACE }}
- THE FIRST CHARACTER OF YOUR RESPONSE MUST BE {{

**REQUIRED JSON FORMAT:**
{{
  "keywords": [
    "keyword1",
    "keyword2",
    ...
  ],
  "experience_highlights": [
    "Specific achievement or bullet to feature prominently",
    "Another key achievement",
    ...
  ],
  "sections_to_expand": [
    "Section name: Specific guidance on what to add or emphasize",
    "Another section: More guidance",
    ...
  ],
  "cover_letter_points": [
    "First talking point addressing a key requirement",
    "Second talking point",
    ...
  ],
  "resume_summary": "Professional summary statement tailored for this role..."
}}

Be specific and actionable. Reference actual content from the resume where possible."""

        return prompt

    def optimize_jobs_batch(
        self, jobs: list, progress_callback: Optional[callable] = None
    ) -> list:
        """
        Optimize resumes for multiple jobs (with multi-threading support)

        Args:
            jobs: List of job dicts (should have match scores and analysis)
            progress_callback: Optional callback function(current, total, job)

        Returns:
            List of jobs with added optimization recommendations
        """
        # Reset failed jobs list
        self.failed_jobs = []

        # Get thread count from environment
        max_workers = int(os.getenv("MATCH_THREADS", "4"))
        total = len(jobs)

        # Get list of already-processed jobs from checkpoint
        processed_urls = set()
        if self.checkpoint_manager:
            processed_urls = set(self.checkpoint_manager.get_processed_urls("optimization"))

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
                # Optimize for the job
                optimization_result = self.optimize_for_job(job)

                if optimization_result:
                    # Add optimization results to job
                    job_with_optimization = {**job, **optimization_result}
                else:
                    # Job failed to optimize, add with empty fields
                    job_with_optimization = {
                        **job,
                        "keywords": [],
                        "experience_highlights": [],
                        "sections_to_expand": [],
                        "cover_letter_points": [],
                        "resume_summary": "",
                    }
                    # Track failure (thread-safe)
                    with progress_lock:
                        self.failed_jobs.append(job)

                # Save checkpoint after each job (thread-safe)
                if self.checkpoint_manager and job_url:
                    self.checkpoint_manager.mark_job_completed("optimization", job_url)

                # Update progress (thread-safe)
                with progress_lock:
                    completed_count[0] += 1
                    if progress_callback:
                        progress_callback(completed_count[0], total, job)

                return job_with_optimization

            except Exception as e:
                print(f"[WARNING] Error optimizing job {job.get('title', 'Unknown')}: {e}")

                # Record failure
                error_msg = f"Thread execution error: {str(e)}"
                if self.failure_tracker:
                    self.failure_tracker.record_failure(job, "optimization", ErrorType.UNKNOWN_ERROR, error_msg)

                # Track failure
                with progress_lock:
                    self.failed_jobs.append(job)

                # Return job with error state
                return {
                    **job,
                    "keywords": [],
                    "experience_highlights": [],
                    "sections_to_expand": [],
                    "cover_letter_points": [],
                    "resume_summary": f"Error during optimization: {str(e)}",
                }

        # Process jobs using smooth batch processor (maintains constant GPU load)
        processor = SmoothBatchProcessor(max_workers=max_workers)
        optimized_jobs = processor.process_batch(jobs_to_process, process_single_job)

        return optimized_jobs

    def optimize_jobs_batch_queued(
        self, jobs: list, progress_callback: Optional[callable] = None
    ) -> list:
        """
        Optimize resumes for multiple jobs using batch queue processing (constant GPU load)

        This method pre-generates all prompts and queues AI requests continuously
        to maintain constant GPU utilization, eliminating power spikes.

        Args:
            jobs: List of job dicts (should have match scores and analysis)
            progress_callback: Optional callback function(current, total, job)

        Returns:
            List of jobs with added optimization recommendations
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
            processed_urls = set(self.checkpoint_manager.get_processed_urls("optimization"))
            jobs_to_process = [job for job in jobs if job.get("job_url", "") not in processed_urls]

        if not jobs_to_process:
            return []

        print(f"\n[INFO] Optimizing {len(jobs_to_process)} jobs (batch queue mode)...\n")

        # Define prompt generator
        def prompt_generator(job: Dict[str, Any]) -> str:
            """Generate optimization prompt for a job"""
            return self._create_optimization_prompt(job)

        # Define AI executor
        def ai_executor(prompt: str) -> Optional[Dict[str, Any]]:
            """Execute AI request for optimization"""
            try:
                response = self.client.generate_json(prompt, temperature=0.5, max_tokens=2048)
                return response
            except Exception:
                return None

        # Define result merger
        def result_merger(job: Dict[str, Any], result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
            """Merge AI result into job dict"""
            if result and isinstance(result, dict):
                # Validate required fields
                required_fields = ["keywords", "experience_highlights", "sections_to_expand", "cover_letter_points", "resume_summary"]
                if all(field in result for field in required_fields):
                    return {
                        **job,
                        "keywords": result.get("keywords", []),
                        "experience_highlights": result.get("experience_highlights", []),
                        "sections_to_expand": result.get("sections_to_expand", []),
                        "cover_letter_points": result.get("cover_letter_points", []),
                        "resume_summary": result.get("resume_summary", ""),
                    }

            # Failure case
            self.failed_jobs.append(job)
            return {
                **job,
                "keywords": [],
                "experience_highlights": [],
                "sections_to_expand": [],
                "cover_letter_points": [],
                "resume_summary": "",
            }

        # Define JSON schema for resume optimization
        json_schema = {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Important keywords from job description"
                },
                "experience_highlights": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key achievements to feature prominently"
                },
                "sections_to_expand": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Resume sections to expand with guidance"
                },
                "cover_letter_points": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key talking points for cover letter"
                },
                "resume_summary": {
                    "type": "string",
                    "description": "Tailored professional summary statement"
                }
            },
            "required": ["keywords", "experience_highlights", "sections_to_expand", "cover_letter_points", "resume_summary"]
        }

        # Create batch queue processor
        processor = BatchQueueProcessor(
            max_workers=max_workers,
            queue_delay_ms=queue_delay_ms
        )

        # Process batch with async batch mode enabled
        optimized_jobs = processor.process_batch(
            jobs=jobs_to_process,
            prompt_generator=prompt_generator,
            ai_executor=ai_executor,
            result_merger=result_merger,
            progress_callback=progress_callback,
            checkpoint_manager=self.checkpoint_manager,
            checkpoint_stage="optimization",
            failure_tracker=self.failure_tracker,
            failure_stage="optimization",
            llama_client=self.client,  # Pass LlamaClient for async batch mode
            temperature=0.5,  # AI generation temperature (higher for creative recommendations)
            max_tokens=2048,  # Max tokens for AI generation
            json_schema=json_schema,  # JSON schema for validation
        )

        return optimized_jobs

    def get_failed_jobs(self) -> List[Dict[str, Any]]:
        """
        Get list of jobs that failed during the last batch optimization

        Returns:
            List of failed job dicts
        """
        return self.failed_jobs

    def get_common_keywords(self, jobs: list, min_frequency: int = 2) -> Dict[str, int]:
        """
        Find keywords that appear across multiple jobs

        Args:
            jobs: List of optimized jobs
            min_frequency: Minimum number of jobs keyword must appear in

        Returns:
            Dict mapping keywords to frequency count
        """
        keyword_counts = {}

        for job in jobs:
            keywords = job.get("keywords", [])
            for keyword in keywords:
                keyword_lower = keyword.lower()
                keyword_counts[keyword_lower] = keyword_counts.get(keyword_lower, 0) + 1

        # Filter by minimum frequency
        return {
            k: v for k, v in keyword_counts.items() if v >= min_frequency
        }

    def get_optimization_summary(self, jobs: list) -> Dict[str, Any]:
        """
        Get summary of optimization recommendations across all jobs

        Args:
            jobs: List of optimized jobs

        Returns:
            Summary dict with common patterns
        """
        if not jobs:
            return {
                "total_jobs": 0,
                "common_keywords": {},
                "avg_keywords_per_job": 0,
            }

        # Get common keywords
        common_keywords = self.get_common_keywords(jobs, min_frequency=2)

        # Calculate averages
        total_keywords = sum(len(job.get("keywords", [])) for job in jobs)
        avg_keywords = round(total_keywords / len(jobs), 1)

        return {
            "total_jobs": len(jobs),
            "common_keywords": dict(sorted(common_keywords.items(), key=lambda x: x[1], reverse=True)[:10]),
            "avg_keywords_per_job": avg_keywords,
        }


if __name__ == "__main__":
    # Test the optimizer
    print("Testing ResumeOptimizer...")

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

    # Create optimizer
    optimizer = ResumeOptimizer(client, analyzer)

    # Test with a sample analyzed job
    sample_job = {
        "title": "Senior Payroll Manager",
        "company": "Test Company",
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
        "strengths": [
            "5+ years payroll experience with multi-state knowledge",
            "Bachelor's degree in Accounting",
            "Advanced Excel and data analysis skills",
        ],
        "gaps": [
            "No Workday HCM experience mentioned",
            "Limited ADP experience details",
        ],
        "assessment": "Good match with strong payroll foundation but should highlight relevant system experience",
    }

    print("\nOptimizing resume for sample job...")
    result = optimizer.optimize_for_job(sample_job)

    if result:
        print("\nOptimization Complete")

        print("\nKeywords to Add:")
        for keyword in result["keywords"]:
            print(f"  • {keyword}")

        print("\nExperience to Highlight:")
        for highlight in result["experience_highlights"]:
            print(f"  [INFO] {highlight}")

        print("\nSections to Expand:")
        for section in result["sections_to_expand"]:
            print(f"  [INFO] {section}")

        print("\nCover Letter Points:")
        for point in result["cover_letter_points"]:
            print(f"  [INFO] {point}")

        print(f"\nSuggested Resume Summary:")
        print(f"  {result['resume_summary']}")
    else:
        print("X Optimization failed")

    print("\nResumeOptimizer test complete")
