#!/usr/bin/env python3
"""
Job Matcher - Main Orchestration Script

AI-powered job matching system that:
1. Scores jobs against resume and requirements
2. Analyzes gaps and strengths
3. Provides resume optimization recommendations
4. Generates HTML reports

Usage:
    python job_matcher.py --input data/jobs_latest.json --min-score 70
    python job_matcher.py --input data/jobs_latest.json --full-pipeline
    python job_matcher.py --report reports/jobs_matched_20251010.json
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.job_matcher import (
    JobTracker,
    LlamaClient,
    ResumeAnalyzer,
    MatchScorer,
    GapAnalyzer,
    ResumeOptimizer,
    ReportGenerator,
    CheckpointManager,
    EmailService,
    FailureTracker,
    ErrorType,
)
from src.core.storage import JobStorage
from src.core.database import get_database

load_dotenv()


class JobMatcherPipeline:
    """Main pipeline for job matching workflow"""

    def __init__(self, enable_checkpoints: bool = True, enable_email: bool = None, use_batch_queue: bool = None):
        """Initialize all components

        Args:
            enable_checkpoints: Enable checkpoint/resume functionality
            enable_email: Override email config (None = use .env setting)
            use_batch_queue: Override batch queue mode (None = use .env setting)
        """
        print("Initializing Job Matcher Pipeline...")

        # Initialize checkpoint manager
        self.checkpoint_manager = CheckpointManager() if enable_checkpoints else None

        # Initialize failure tracker
        self.failure_tracker = FailureTracker()

        # Initialize components
        # Get active profile for profile-aware components
        self.profile_name = os.getenv("ACTIVE_PROFILE", "default")

        # Initialize storage and database
        self.storage = JobStorage(profile_name=self.profile_name)
        self.db = get_database(self.profile_name)

        # Process any pending database writes from previous failed saves
        self._process_pending_writes()

        self.tracker = JobTracker()
        self.client = LlamaClient()
        self.analyzer = ResumeAnalyzer()
        self.scorer = MatchScorer(self.client, self.analyzer, self.checkpoint_manager, self.failure_tracker)
        self.gap_analyzer = GapAnalyzer(self.client, self.analyzer, self.checkpoint_manager, self.failure_tracker)
        self.optimizer = ResumeOptimizer(self.client, self.analyzer, self.checkpoint_manager, self.failure_tracker)
        self.report_gen = ReportGenerator()
        self.email_service = EmailService(profile_name=self.profile_name)

        # Configuration
        self.min_score = int(os.getenv("MIN_MATCH_SCORE", "60"))

        # Batch queue configuration (for constant GPU load)
        self.use_batch_queue = use_batch_queue if use_batch_queue is not None else os.getenv("BATCH_QUEUE_MODE", "true").lower() == "true"

        # Email configuration
        self.email_enabled = enable_email if enable_email is not None else os.getenv("EMAIL_ENABLED", "false").lower() == "true"
        # Parse multiple email recipients (comma-separated)
        email_recipient_str = os.getenv("EMAIL_RECIPIENT", "")
        self.email_recipients = [email.strip() for email in email_recipient_str.split(',') if email.strip()] if email_recipient_str else []
        self.email_send_on_completion = os.getenv("EMAIL_SEND_ON_COMPLETION", "true").lower() == "true"
        self.email_min_matches = int(os.getenv("EMAIL_MIN_MATCHES", "1"))
        self.email_subject_prefix = os.getenv("EMAIL_SUBJECT_PREFIX", "[Job Matcher]")

        # Job source detection
        self.job_source = "indeed"  # Default source

        # SQL filter tracking (set by load_jobs_from_db when SQL filters are applied)
        self._sql_filters_applied = False

        print("Pipeline initialized")

    def detect_source_from_filename(self, filename: str) -> str:
        """
        Detect job source from input filename

        Args:
            filename: Input file path

        Returns:
            Source identifier (e.g., "indeed", "linkedin")
        """
        filename_lower = Path(filename).name.lower()

        # Check for source identifiers in filename
        if "indeed" in filename_lower:
            return "indeed"
        elif "linkedin" in filename_lower:
            return "linkedin"
        elif "ziprecruiter" in filename_lower:
            return "ziprecruiter"
        elif "glassdoor" in filename_lower:
            return "glassdoor"
        else:
            # Default to indeed for backward compatibility
            return "indeed"

    def _process_pending_writes(self):
        """Process any pending database writes from previous failed saves."""
        try:
            from src.core.pending_writes import get_pending_manager
            pending_manager = get_pending_manager(self.profile_name)
            stats = pending_manager.get_pending_stats()
            if stats["file_count"] > 0:
                print(f"[INFO] Found {stats['file_count']} pending write files ({stats['total_records']} records)")
                result = pending_manager.process_pending(self.storage)
                print(f"[INFO] Processed pending writes: {result['processed']} records, {result['failed']} failed")
        except Exception as e:
            print(f"[WARNING] Failed to process pending writes: {e}")

    def load_jobs(self, input_file: str) -> List[Dict[str, Any]]:
        """
        Load jobs from DuckDB or JSON file

        Args:
            input_file: Path to JSON file or source identifier (e.g., "glassdoor")

        Returns:
            List of job dicts
        """
        # Check if input_file is a source identifier (not a file path)
        source_identifiers = ["indeed", "glassdoor", "linkedin", "ziprecruiter"]
        if input_file.lower() in source_identifiers:
            return self.load_jobs_from_db(input_file.lower())

        # Check if it looks like a source pattern in the filename
        for source in source_identifiers:
            if source in input_file.lower():
                print(f"\nLoading jobs from database (source: {source})...")
                jobs = self.load_jobs_from_db(source)
                if jobs:
                    print(f"Loaded {len(jobs)} jobs from database")
                    return jobs
                # Fall through to file loading if DB is empty
                break

        # Fall back to file loading for backward compatibility
        print(f"\nLoading jobs from file: {input_file}")

        if not Path(input_file).exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        with open(input_file, "r", encoding="utf-8") as f:
            jobs = json.load(f)

        # Mark that SQL filters were NOT applied (file loading doesn't use SQL)
        self._sql_filters_applied = False

        print(f"Loaded {len(jobs)} jobs from file")
        return jobs

    def load_jobs_from_db(self, source: str, use_sql_filters: bool = True) -> List[Dict[str, Any]]:
        """
        Load unprocessed jobs from DuckDB with optional SQL-based pre-filtering

        Args:
            source: Job source identifier (e.g., "glassdoor", "indeed")
            use_sql_filters: If True, apply deterministic filters at SQL level (much faster)

        Returns:
            List of job dicts
        """
        if use_sql_filters:
            # Extract filter parameters from analyzer
            candidate_profile = self.analyzer.candidate_profile
            preferences = self.analyzer.preferences

            # Build title keywords from target roles and related keywords
            title_keywords = []
            target_roles = candidate_profile.get("target_roles", [])
            related_keywords = candidate_profile.get("related_keywords", [])

            # Extract individual words from target roles
            for role in target_roles:
                words = role.lower().split()
                title_keywords.extend(words)
            title_keywords.extend([k.lower() for k in related_keywords])

            # Remove stop words and duplicates
            stop_words = {"and", "or", "the", "a", "an", "for", "to", "of", "in", "with"}
            title_keywords = list(set(k for k in title_keywords if k not in stop_words))

            # Get exclude keywords
            title_exclude_keywords = candidate_profile.get("title_exclude_keywords", [])

            # Get other filter parameters
            min_salary = preferences.get("min_salary")
            max_salary = preferences.get("max_salary")
            remote_only = preferences.get("remote_only", False)
            job_types = preferences.get("job_types", [])
            locations = preferences.get("locations", [])
            max_job_age_days = preferences.get("max_job_age_days", 30)

            # Check which filters are enabled via .env
            if os.getenv('FILTER_TITLE_ENABLED', 'true').lower() != 'true':
                title_keywords = None
                title_exclude_keywords = None
            if os.getenv('FILTER_SALARY_ENABLED', 'true').lower() != 'true':
                min_salary = None
                max_salary = None
            if os.getenv('FILTER_REMOTE_ENABLED', 'true').lower() != 'true':
                remote_only = False
            if os.getenv('FILTER_JOB_TYPE_ENABLED', 'true').lower() != 'true':
                job_types = None
            if os.getenv('FILTER_LOCATION_ENABLED', 'true').lower() != 'true':
                locations = None
            if os.getenv('FILTER_POSTING_AGE_ENABLED', 'true').lower() != 'true':
                max_job_age_days = None

            print(f"\n🔍 Applying SQL-based filters to database...")
            df, stats = self.storage.load_unprocessed_jobs_filtered(
                source=source,
                title_keywords=title_keywords if title_keywords else None,
                title_exclude_keywords=title_exclude_keywords if title_exclude_keywords else None,
                min_salary=min_salary,
                max_salary=max_salary,
                remote_only=remote_only,
                job_types=job_types if job_types else None,
                locations=locations if locations else None,
                max_job_age_days=max_job_age_days,
            )

            # Print filter stats
            print(f"✅ SQL filters passed: {stats['passed_jobs']} jobs")
            print(f"❌ SQL filters rejected: {stats['rejected_jobs']} jobs")
            print(f"📊 Pass rate: {stats['pass_rate']*100:.1f}%")

            # Mark that SQL filtering was done (so Python filters can be skipped)
            self._sql_filters_applied = True

            if df is None or df.empty:
                return []
        else:
            self._sql_filters_applied = False
            df = self.storage.load_unprocessed_jobs(source)
            if df is None or df.empty:
                return []

        # Convert DataFrame to list of dicts
        jobs = df.to_dict("records")

        # Convert array columns back to lists (DuckDB returns them as numpy arrays)
        list_fields = ['skills', 'requirements', 'benefits', 'work_arrangements']
        for job in jobs:
            for field in list_fields:
                if field in job and job[field] is not None:
                    # Convert numpy array or other iterable to list
                    try:
                        job[field] = list(job[field]) if job[field] is not None else []
                    except (TypeError, ValueError):
                        job[field] = []

        # Convert timestamp fields to ISO strings for JSON serialization
        timestamp_fields = ['first_seen', 'last_seen']
        for job in jobs:
            for field in timestamp_fields:
                if field in job and job[field] is not None:
                    if hasattr(job[field], 'isoformat'):
                        job[field] = job[field].isoformat()

        return jobs

    def filter_unprocessed_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out already-processed jobs

        Args:
            jobs: List of job dicts

        Returns:
            List of unprocessed jobs
        """
        print("\nFiltering already-processed jobs...")

        unprocessed = []
        for job in jobs:
            job_url = job.get("job_url", "")
            if not self.tracker.is_processed(job_url):
                unprocessed.append(job)

        skipped = len(jobs) - len(unprocessed)
        print(f"{len(unprocessed)} unprocessed, {skipped} already processed")

        return unprocessed

    def run_scoring_pass(
        self, jobs: List[Dict[str, Any]], min_score: Optional[int] = None,
        api_progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Pass 1: Score jobs against resume and requirements

        Args:
            jobs: List of job dicts
            min_score: Minimum score threshold (default: from config)
            api_progress_callback: Optional callback for API progress updates
                                   Signature: (current: int, total: int, message: str) -> None

        Returns:
            List of matched jobs (score >= min_score)
        """
        min_score = min_score or self.min_score

        print(f"\n{'=' * 80}")
        print("PASS 1: SCORING JOBS")
        print(f"{'=' * 80}")
        print(f"Minimum match score: {min_score}")
        print(f"Jobs to score: {len(jobs)}")
        print()

        total_jobs = len(jobs)

        def progress_callback(current, total, job):
            title = job.get("title", "Unknown")[:50]
            print(f"[{current}/{total}] Scoring: {title}...")
            # Call API progress callback if provided
            if api_progress_callback:
                api_progress_callback(current, total_jobs, f"Scoring job {current}/{total_jobs}: {title}")

        # Skip Python pre-filters if SQL filters were already applied at load time
        apply_pre_filters = not getattr(self, '_sql_filters_applied', False)
        if not apply_pre_filters:
            print("(SQL pre-filters already applied, skipping Python filters)")

        print(f"Scoring jobs (batch queue mode: {self.use_batch_queue})...")
        if self.use_batch_queue:
            scored_jobs = self.scorer.score_jobs_batch_queued(jobs, progress_callback, apply_pre_filters=apply_pre_filters)
        else:
            scored_jobs = self.scorer.score_jobs_batch(jobs, progress_callback, apply_pre_filters=apply_pre_filters)

        # Filter by minimum score
        print(f"\nFiltering jobs with score >= {min_score}...", flush=True)
        matched, rejected = self.scorer.filter_by_score(scored_jobs, min_score)
        print(f"   {len(matched)} matched, {len(rejected)} rejected", flush=True)

        # Get title-filtered jobs
        title_rejected = self.scorer.get_rejected_jobs()

        # Get deterministic-filtered jobs
        filtered_jobs = self.scorer.get_filtered_jobs()

        # Export failed jobs
        failed_jobs = self.scorer.get_failed_jobs()
        if failed_jobs:
            print(f"   Exporting {len(failed_jobs)} failed jobs...", flush=True)
            self.export_failed_jobs("scoring", failed_jobs)

        # Export rejected jobs (below threshold) for manual review
        rejected_file = None
        if rejected:
            print(f"   Saving {len(rejected)} rejected jobs to file...", flush=True)
            rejected_file = self.save_rejected_jobs(rejected)
            print(f"   Saved to {rejected_file}", flush=True)

        # Mark ALL processed jobs as tracked (matched, rejected, filtered)
        # This prevents re-processing on subsequent runs
        print("\nMarking all processed jobs in tracker...", flush=True)
        all_processed_jobs = matched + rejected + title_rejected + filtered_jobs + failed_jobs
        self.update_tracker_all_jobs(all_processed_jobs, default_score=0)
        print(f"[SUCCESS] Marked {len(all_processed_jobs)} jobs as processed")

        print(f"\nPass 1 Complete")
        print(f"   Deterministic Filters: {len(filtered_jobs)} jobs rejected")
        print(f"   Title Filter: {len(title_rejected)} jobs rejected (irrelevant job titles)")
        print(f"   AI Scored: {len(scored_jobs)} jobs")
        print(f"   Matched: {len(matched)} jobs (score >= {min_score})")
        print(f"   Rejected: {len(rejected)} jobs (score < {min_score})")
        if rejected_file:
            print(f"   Rejected jobs saved to: {rejected_file}")
        print(f"   Failed: {len(failed_jobs)} jobs")

        return matched

    def run_analysis_pass(
        self, jobs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Pass 2: Analyze gaps and strengths

        Args:
            jobs: List of scored jobs

        Returns:
            List of analyzed jobs
        """
        print(f"\n{'=' * 80}")
        print("PASS 2: GAP ANALYSIS")
        print(f"{'=' * 80}")
        print(f"Jobs to analyze: {len(jobs)}")
        print()

        def progress_callback(current, total, job):
            title = job.get("title", "Unknown")[:50]
            score = job.get("match_score", 0)
            print(f"[{current}/{total}] Analyzing: {title} (Score: {score})...")

        if self.use_batch_queue:
            analyzed_jobs = self.gap_analyzer.analyze_jobs_batch_queued(jobs, progress_callback)
        else:
            analyzed_jobs = self.gap_analyzer.analyze_jobs_batch(jobs, progress_callback)

        # Export failed jobs
        failed_jobs = self.gap_analyzer.get_failed_jobs()
        if failed_jobs:
            self.export_failed_jobs("analysis", failed_jobs)

        stats = self.gap_analyzer.get_summary_stats(analyzed_jobs)

        print(f"\nPass 2 Complete")
        print(f"   Avg strengths per job: {stats['avg_strengths']}")
        print(f"   Avg gaps per job: {stats['avg_gaps']}")
        print(f"   Jobs with red flags: {stats['jobs_with_red_flags']}")
        print(f"   Failed: {len(failed_jobs)} jobs")

        return analyzed_jobs

    def run_optimization_pass(
        self, jobs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Pass 3: Generate resume recommendations

        Args:
            jobs: List of analyzed jobs

        Returns:
            List of optimized jobs
        """
        print(f"\n{'=' * 80}")
        print("PASS 3: RESUME OPTIMIZATION")
        print(f"{'=' * 80}")
        print(f"Jobs to optimize: {len(jobs)}")
        print()

        def progress_callback(current, total, job):
            title = job.get("title", "Unknown")[:50]
            score = job.get("match_score", 0)
            print(f"[{current}/{total}] Optimizing: {title} (Score: {score})...")

        if self.use_batch_queue:
            optimized_jobs = self.optimizer.optimize_jobs_batch_queued(jobs, progress_callback)
        else:
            optimized_jobs = self.optimizer.optimize_jobs_batch(jobs, progress_callback)

        # Export failed jobs
        failed_jobs = self.optimizer.get_failed_jobs()
        if failed_jobs:
            self.export_failed_jobs("optimization", failed_jobs)

        summary = self.optimizer.get_optimization_summary(optimized_jobs)

        print(f"\nPass 3 Complete")
        print(f"   Avg keywords per job: {summary['avg_keywords_per_job']}")
        if summary['common_keywords']:
            print(f"   Top common keywords:")
            for keyword, count in list(summary['common_keywords'].items())[:5]:
                print(f"     - {keyword}: appears in {count} jobs")
        print(f"   Failed: {len(failed_jobs)} jobs")

        return optimized_jobs

    def save_matched_jobs(
        self, jobs: List[Dict[str, Any]], output_file: Optional[str] = None
    ) -> str:
        """
        Save matched jobs to DuckDB and optionally to JSON file

        Args:
            jobs: List of job dicts with match results
            output_file: Optional output filename for JSON backup

        Returns:
            Path to saved JSON file (for report generation)
        """
        # Update match results in DuckDB using batch operation
        print("\nUpdating match results in database...")

        # Prepare jobs for batch update
        jobs_to_update = []
        for job in jobs:
            job_url = job.get("job_url")
            if not job_url:
                continue

            match_score = job.get("match_score")
            if match_score is None:
                continue

            match_explanation = job.get("match_explanation", "")
            is_relevant = job.get("is_relevant", True)

            # Build gap_analysis from component fields if not already present
            gap_analysis = job.get("gap_analysis")
            if gap_analysis is None:
                # Check if we have the component fields from GapAnalyzer
                if any(job.get(field) is not None for field in ["strengths", "gaps", "red_flags", "assessment"]):
                    gap_analysis = {
                        "strengths": job.get("strengths", []),
                        "gaps": job.get("gaps", []),
                        "red_flags": job.get("red_flags", []),
                        "assessment": job.get("assessment", ""),
                    }

            # Build resume_suggestions from component fields if not already present
            resume_suggestions = job.get("resume_suggestions")
            if resume_suggestions is None:
                # Check if we have the component fields from ResumeOptimizer
                if any(job.get(field) is not None for field in ["keywords", "experience_highlights", "sections_to_expand", "cover_letter_points", "resume_summary"]):
                    resume_suggestions = {
                        "keywords": job.get("keywords", []),
                        "experience_highlights": job.get("experience_highlights", []),
                        "sections_to_expand": job.get("sections_to_expand", []),
                        "cover_letter_points": job.get("cover_letter_points", []),
                        "resume_summary": job.get("resume_summary", ""),
                    }

            # Handle gap_analysis and resume_suggestions which might be dicts
            if isinstance(gap_analysis, dict):
                gap_analysis = json.dumps(gap_analysis)
            if isinstance(resume_suggestions, dict):
                resume_suggestions = json.dumps(resume_suggestions)

            jobs_to_update.append({
                "job_url": job_url,
                "match_score": match_score,
                "match_explanation": match_explanation,
                "is_relevant": is_relevant,
                "gap_analysis": gap_analysis,
                "resume_suggestions": resume_suggestions,
            })

        # Batch update all jobs
        result = self.storage.update_match_results_batch(jobs_to_update)
        print(f"Updated {result['updated']} jobs in database ({result.get('failed', 0)} failed)")

        # Also save to JSON file for report generation and backward compatibility
        if not output_file:
            from src.utils.profile_manager import ProfilePaths
            paths = ProfilePaths()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = str(paths.data_dir / f"jobs_{self.job_source}_matched_{timestamp}.json")

        # Ensure data directory exists
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)

        print(f"[INFO] Matched jobs also saved to: {output_file}")

        # Update checkpoint with output file path
        if self.checkpoint_manager:
            self.checkpoint_manager.update_output_file("matched_jobs", output_file)

        return output_file

    def export_failed_jobs(self, stage: str, failed_jobs: List[Dict[str, Any]]) -> Optional[str]:
        """
        Export failed jobs to JSON file for retry

        Args:
            stage: Pipeline stage (scoring, analysis, optimization)
            failed_jobs: List of failed job dicts

        Returns:
            Path to exported file or None if no failures
        """
        if not failed_jobs:
            return None

        from src.utils.profile_manager import ProfilePaths
        paths = ProfilePaths()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = str(paths.data_dir / f"jobs_{self.job_source}_failed_{stage}_{timestamp}.json")

        # Ensure data directory exists
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        # Export using failure tracker with metadata
        count = self.failure_tracker.export_failed_jobs(stage, output_file, include_metadata=True)

        if count > 0:
            print(f"\n[WARNING] Exported {count} failed jobs to: {output_file}")
            return output_file

        return None

    def save_rejected_jobs(self, rejected_jobs: List[Dict[str, Any]]) -> Optional[str]:
        """
        Save rejected jobs (below threshold) to JSON file for manual review

        Args:
            rejected_jobs: List of job dicts that scored below threshold

        Returns:
            Path to saved file or None if no rejected jobs
        """
        if not rejected_jobs:
            return None

        from src.utils.profile_manager import ProfilePaths
        paths = ProfilePaths()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = str(paths.data_dir / f"jobs_{self.job_source}_rejected_{timestamp}.json")

        # Ensure data directory exists
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(rejected_jobs, f, indent=2, ensure_ascii=False)

        print(f"\n[INFO] Rejected jobs (below threshold) saved to: {output_file}")

        return output_file

    def load_checkpoint_data(self, input_file: str) -> Optional[List[Dict[str, Any]]]:
        """
        Load partial results from checkpoint

        Args:
            input_file: Path to input jobs file

        Returns:
            List of partially-processed jobs or None
        """
        if not self.checkpoint_manager:
            return None

        checkpoint = self.checkpoint_manager.load_checkpoint(input_file)
        if not checkpoint:
            return None

        # Load partial results from matched_jobs file
        output_file = self.checkpoint_manager.get_output_file("matched_jobs")
        if output_file and Path(output_file).exists():
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[WARNING] Failed to load checkpoint data: {e}")
                return None

        return None

    def update_tracker(self, jobs: List[Dict[str, Any]]):
        """
        Update job tracker with processed jobs

        Args:
            jobs: List of job dicts with match scores
        """
        print("\nUpdating job tracker...")

        for job in jobs:
            self.tracker.add_job(
                job_url=job.get("job_url", ""),
                job_title=job.get("title", "Unknown"),
                company=job.get("company", "Unknown"),
                location=job.get("location", "Unknown"),
                match_score=job.get("match_score", 0),
            )

        print("Job tracker updated")

    def update_tracker_all_jobs(self, jobs: List[Dict[str, Any]], default_score: int = 0):
        """
        Update job tracker with all processed jobs (including rejected/filtered)

        This method marks ALL jobs as processed to prevent re-processing in future runs.
        Use default_score for jobs that were filtered/rejected before AI scoring.

        Args:
            jobs: List of job dicts (may or may not have match_score)
            default_score: Default score for jobs without match_score (default: 0)
        """
        if not jobs:
            return

        # Use batch operation to minimize DB lock contention
        result = self.tracker.add_jobs_batch(jobs, default_score=default_score)
        print(f"   Tracker updated: {result['inserted']} new, {result['updated']} updated")

    def generate_report(
        self, jobs: List[Dict[str, Any]], report_title: Optional[str] = None, source_file: Optional[str] = None
    ) -> str:
        """
        Generate HTML report

        Args:
            jobs: List of fully processed jobs
            report_title: Optional report title
            source_file: Optional path to source JSON file (for metadata reference)

        Returns:
            Path to generated report
        """
        print(f"\n{'=' * 80}")
        print("GENERATING REPORT")
        print(f"{'=' * 80}")

        if not report_title:
            report_title = f"Job Match Report - {self.job_source.title()} - {datetime.now().strftime('%B %d, %Y')}"

        report_path = self.report_gen.generate_report(jobs, report_title, source_file=source_file, source=self.job_source)

        print(f"\nReport generated: {report_path}")

        return report_path

    def send_email_report(
        self, jobs: List[Dict[str, Any]], report_path: str
    ) -> bool:
        """
        Send email with job match report to all configured recipients

        Args:
            jobs: List of matched jobs
            report_path: Path to HTML report

        Returns:
            True if email sent successfully to at least one recipient, False otherwise
        """
        # Check if email is enabled
        if not self.email_enabled or not self.email_send_on_completion:
            return False

        # Check if we have enough matches
        if len(jobs) < self.email_min_matches:
            print(f"\n[INFO] Skipping email: Only {len(jobs)} matches (minimum: {self.email_min_matches})")
            return False

        # Check if recipients are configured
        if not self.email_recipients:
            print("\n[WARNING] Email recipients not configured. Run 'python setup_email.py'")
            return False

        # Check if email service is configured
        if not self.email_service.is_configured():
            print("\n[WARNING] Email service not configured. Run 'python setup_email.py'")
            return False

        print(f"\n{'=' * 80}")
        print("SENDING EMAIL REPORT")
        print(f"{'=' * 80}")
        print(f"Recipients: {', '.join(self.email_recipients)}")
        print(f"Matches: {len(jobs)}")
        print()

        # Send email to each recipient
        all_success = True
        for recipient in self.email_recipients:
            print(f"Sending to {recipient}...")
            success = self.email_service.send_report(
                recipient=recipient,
                jobs=jobs,
                report_path=report_path,
                subject_prefix=self.email_subject_prefix,
            )

            if not success:
                all_success = False
                print(f"  ✗ Failed to send to {recipient}")
            # Success message is printed by email_service

        if all_success:
            print(f"\n[SUCCESS] Email sent successfully to all {len(self.email_recipients)} recipient(s)")
        else:
            print(f"\n[WARNING] Some emails failed to send")

        return all_success

    def run_full_pipeline(
        self,
        input_file: str,
        min_score: Optional[int] = None,
        skip_processed: bool = True,
        resume_from_checkpoint: bool = False,
    ) -> str:
        """
        Run complete pipeline: load -> score -> analyze -> optimize -> report

        Args:
            input_file: Path to jobs JSON file
            min_score: Minimum match score threshold
            skip_processed: Skip already-processed jobs
            resume_from_checkpoint: Resume from checkpoint if available

        Returns:
            Path to generated report
        """
        min_score = min_score or self.min_score

        # Check for existing checkpoint
        resuming = False
        if resume_from_checkpoint and self.checkpoint_manager:
            if self.checkpoint_manager.has_checkpoint(input_file):
                print("\n" + "=" * 80)
                print("CHECKPOINT FOUND")
                print("=" * 80)
                print(self.checkpoint_manager.get_summary())
                print("=" * 80)
                response = input("\nResume from checkpoint? (y/n): ").strip().lower()
                if response == 'y':
                    resuming = True
                else:
                    print("Starting fresh pipeline...")
                    self.checkpoint_manager.clear_checkpoint()

        print(f"\n{'=' * 80}")
        print("JOB MATCHER - FULL PIPELINE")
        if resuming:
            print("(RESUMING FROM CHECKPOINT)")
        print(f"{'=' * 80}")
        print(f"Input: {input_file}")
        print(f"Min Score: {min_score}")
        print(f"Skip Processed: {skip_processed}")
        print(f"{'=' * 80}")

        # Detect job source from input filename
        self.job_source = self.detect_source_from_filename(input_file)
        print(f"\nDetected job source: {self.job_source}")

        # Load resume and requirements
        print("\nLoading resume and requirements...")
        if not self.analyzer.load_all():
            raise RuntimeError("Failed to load resume and requirements")
        print("Resume and requirements loaded")

        # Test llama-server connection
        print("\nTesting llama-server connection...")
        if not self.client.test_connection():
            raise RuntimeError(
                "Failed to connect to llama-server. Is it running at "
                f"{self.client.server_url}?"
            )
        print("Connected to llama-server")

        # Initialize or resume from checkpoint
        matched_jobs = []
        analyzed_jobs = []
        optimized_jobs = []
        matched_file = None

        if resuming:
            # Load checkpoint and partial results
            partial_jobs = self.load_checkpoint_data(input_file)
            if partial_jobs:
                print(f"Loaded {len(partial_jobs)} jobs from checkpoint")
                matched_jobs = partial_jobs
                matched_file = self.checkpoint_manager.get_output_file("matched_jobs")
            else:
                print("[WARNING] Could not load checkpoint data, starting fresh")
                resuming = False
                if self.checkpoint_manager:
                    self.checkpoint_manager.clear_checkpoint()

        # Load jobs
        jobs = self.load_jobs(input_file)

        # Filter already-processed jobs if requested
        if skip_processed:
            jobs = self.filter_unprocessed_jobs(jobs)

        if not jobs and not resuming:
            print("\n[WARNING] No jobs to process!")
            return ""

        # Create checkpoint if not resuming
        if not resuming and self.checkpoint_manager:
            self.checkpoint_manager.create_checkpoint(input_file, min_score)

        # Clear previous run failures (start fresh for this pipeline)
        if not resuming:
            self.failure_tracker.reset()

        # Pass 1: Scoring (skip if already completed in checkpoint)
        if not resuming or not self.checkpoint_manager.is_stage_completed("scoring"):
            matched_jobs = self.run_scoring_pass(jobs, min_score)

            if not matched_jobs:
                print("\n[WARNING] No jobs met the minimum score threshold!")
                if self.checkpoint_manager:
                    self.checkpoint_manager.clear_checkpoint()
                return ""

            # Save matched jobs
            matched_file = self.save_matched_jobs(matched_jobs, matched_file)

            # Mark scoring stage as complete
            if self.checkpoint_manager:
                self.checkpoint_manager.mark_stage_completed("scoring", len(matched_jobs))
        else:
            print(f"\nScoring already complete ({len(matched_jobs)} matched jobs)")

        # Pass 2: Gap Analysis (skip if already completed in checkpoint)
        if not resuming or not self.checkpoint_manager.is_stage_completed("analysis"):
            analyzed_jobs = self.run_analysis_pass(matched_jobs)

            # Save updated jobs after analysis
            self.save_matched_jobs(analyzed_jobs, matched_file)

            # Mark analysis stage as complete
            if self.checkpoint_manager:
                self.checkpoint_manager.mark_stage_completed("analysis")
        else:
            analyzed_jobs = matched_jobs
            print(f"\nAnalysis already complete ({len(analyzed_jobs)} jobs)")

        # Pass 3: Resume Optimization (skip if already completed in checkpoint)
        if not resuming or not self.checkpoint_manager.is_stage_completed("optimization"):
            optimized_jobs = self.run_optimization_pass(analyzed_jobs)

            # Save final jobs after optimization
            self.save_matched_jobs(optimized_jobs, matched_file)

            # Mark optimization stage as complete
            if self.checkpoint_manager:
                self.checkpoint_manager.mark_stage_completed("optimization")
        else:
            optimized_jobs = analyzed_jobs
            print(f"\nOptimization already complete ({len(optimized_jobs)} jobs)")

        # Update tracker
        self.update_tracker(optimized_jobs)

        # Generate report (pass source file for metadata reference)
        report_path = self.generate_report(optimized_jobs, source_file=matched_file)

        # Send email if enabled
        self.send_email_report(optimized_jobs, report_path)

        # Clear checkpoint after successful completion
        if self.checkpoint_manager:
            self.checkpoint_manager.clear_checkpoint()

        # Get failure statistics
        failure_stats = self.failure_tracker.get_failure_stats()

        # Final summary
        print(f"\n{'=' * 80}")
        print("PIPELINE COMPLETE")
        print(f"{'=' * 80}")
        print(f"Processed {len(jobs) if not resuming else len(optimized_jobs)} jobs")
        print(f"Found {len(matched_jobs)} matches")
        print(f"Report: {report_path}")
        if self.email_enabled and self.email_recipients:
            email_status = "sent" if len(optimized_jobs) >= self.email_min_matches else "skipped (too few matches)"
            print(f"Email: {email_status}")

        # Display failure summary if there were failures
        if failure_stats["total_failures"] > 0:
            print(f"\n[WARNING] Failures: {failure_stats['total_failures']} jobs failed processing")
            print(f"   By stage:")
            for stage, count in failure_stats["by_stage"].items():
                print(f"     - {stage}: {count}")
            print(f"   By error type:")
            for error_type, count in failure_stats["by_error_type"].items():
                print(f"     - {error_type}: {count}")

            # Show sample errors (max 3)
            sample_errors = self.failure_tracker.get_sample_errors(limit=3)
            if sample_errors:
                print(f"\n   Sample errors:")
                for sample in sample_errors:
                    job_title = sample['job_title'][:40]  # Truncate long titles
                    error_type = sample['error_type']
                    error_msg = sample['error_message'][:60]  # Truncate long messages
                    print(f"     • {job_title} ({error_type})")
                    if error_msg:
                        print(f"       {error_msg}...")

            print(f"\n   Use --failure-stats to see detailed failure information")

        print(f"{'=' * 80}\n")

        return report_path

    def process_all_sources(
        self,
        min_score: Optional[int] = None,
        skip_processed: bool = True,
        resume_from_checkpoint: bool = False,
    ) -> List[tuple]:
        """
        Process all sources from DuckDB or data/ directory

        Args:
            min_score: Minimum match score threshold
            skip_processed: Skip already-processed jobs
            resume_from_checkpoint: Resume from checkpoint if available

        Returns:
            List of tuples: [(source, report_path, matched_jobs), ...]
        """
        # First check DuckDB for available sources
        source_files = []
        for source in ["indeed", "glassdoor", "linkedin", "ziprecruiter"]:
            job_count = self.storage.get_job_count(source)
            if job_count > 0:
                # Use source name as identifier (will be loaded from DB)
                source_files.append((source, source))

        # Also check for legacy JSON files if no DB sources found
        if not source_files:
            data_dir = Path("data")
            for source in ["indeed", "glassdoor", "linkedin", "ziprecruiter"]:
                source_file = data_dir / f"jobs_{source}_latest.json"
                if source_file.exists():
                    source_files.append((source, str(source_file)))

        if not source_files:
            print("\n[WARNING] No source files found in data/ directory")
            print("   Expected: jobs_indeed_latest.json, jobs_glassdoor_latest.json, etc.")
            return []

        print(f"\n{'=' * 80}")
        print("MULTI-SOURCE PROCESSING")
        print(f"{'=' * 80}")
        print(f"Found {len(source_files)} source file(s):")
        for source, filepath in source_files:
            print(f"  - {source}: {filepath}")
        print(f"{'=' * 80}\n")

        results = []

        for source, filepath in source_files:
            print(f"\n{'#' * 80}")
            print(f"# Processing {source.upper()}")
            print(f"{'#' * 80}\n")

            try:
                # Run full pipeline for this source
                report_path = self.run_full_pipeline(
                    filepath,
                    min_score=min_score,
                    skip_processed=skip_processed,
                    resume_from_checkpoint=resume_from_checkpoint,
                )

                if report_path:
                    # Load matched jobs from DuckDB
                    df = self.storage.load_matched_jobs(source, min_score or self.min_score)
                    if df is not None and not df.empty:
                        matched_jobs = df.to_dict("records")
                        # Convert timestamp fields to ISO strings for JSON serialization
                        for job in matched_jobs:
                            for field in ['first_seen', 'last_seen']:
                                if field in job and job[field] is not None:
                                    if hasattr(job[field], 'isoformat'):
                                        job[field] = job[field].isoformat()
                    else:
                        # Fallback to JSON file if DB is empty
                        matched_file = f"data/jobs_{source}_matched_{datetime.now().strftime('%Y%m%d')}_*.json"
                        import glob
                        matched_files = glob.glob(matched_file)

                        matched_jobs = []
                        if matched_files:
                            # Get most recent matched file
                            latest_matched = max(matched_files, key=lambda f: Path(f).stat().st_mtime)
                            with open(latest_matched, 'r', encoding='utf-8') as f:
                                matched_jobs = json.load(f)

                    results.append((source, report_path, matched_jobs))
                    print(f"\n[SUCCESS] {source.upper()} processing complete")
                else:
                    print(f"\n[WARNING] {source.upper()} processing returned no results")

            except Exception as e:
                print(f"\n[ERROR] Error processing {source}: {e}")
                import traceback
                traceback.print_exc()
                continue

        return results

    def send_multi_source_email_report(
        self,
        source_results: List[tuple]
    ) -> bool:
        """
        Send email with multi-source job match reports

        Args:
            source_results: List of tuples [(source, report_path, matched_jobs), ...]

        Returns:
            True if email sent successfully to at least one recipient, False otherwise
        """
        # Check if email is enabled
        if not self.email_enabled or not self.email_send_on_completion:
            return False

        # Calculate total matches across all sources
        total_matches = sum(len(jobs) for _, _, jobs in source_results)

        # Check if we have enough matches
        if total_matches < self.email_min_matches:
            print(f"\n[INFO] Skipping email: Only {total_matches} total matches (minimum: {self.email_min_matches})")
            return False

        # Check if recipients are configured
        if not self.email_recipients:
            print("\n[WARNING] Email recipients not configured. Run 'python setup_email.py'")
            return False

        # Check if email service is configured
        if not self.email_service.is_configured():
            print("\n[WARNING] Email service not configured. Run 'python setup_email.py'")
            return False

        print(f"\n{'=' * 80}")
        print("SENDING MULTI-SOURCE EMAIL REPORT")
        print(f"{'=' * 80}")
        print(f"Recipients: {', '.join(self.email_recipients)}")
        print(f"Total Matches: {total_matches}")
        for source, _, jobs in source_results:
            print(f"  - {source}: {len(jobs)} matches")
        print()

        # Collect all report paths
        report_paths = [report_path for _, report_path, _ in source_results]

        # Flatten all jobs with source info
        all_jobs = []
        for source, _, jobs in source_results:
            # Add source metadata to each job for email grouping
            for job in jobs:
                job['_email_source'] = source
                all_jobs.append(job)

        # Send email to each recipient
        all_success = True
        for recipient in self.email_recipients:
            print(f"Sending to {recipient}...")
            success = self.email_service.send_multi_source_report(
                recipient=recipient,
                jobs_by_source=[(source, jobs) for source, _, jobs in source_results],
                report_paths=report_paths,
                subject_prefix=self.email_subject_prefix,
            )

            if not success:
                all_success = False
                print(f"  ✗ Failed to send to {recipient}")

        if all_success:
            print(f"\n[SUCCESS] Email sent successfully to all {len(self.email_recipients)} recipient(s)")
        else:
            print(f"\n[WARNING] Some emails failed to send")

        return all_success


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="AI-Powered Job Matching and Resume Optimization"
    )

    parser.add_argument(
        "--input",
        type=str,
        default="data/jobs_indeed_latest.json",
        help="Input JSON file with jobs",
    )

    parser.add_argument(
        "--min-score",
        type=int,
        help="Minimum match score threshold (default: from .env)",
    )

    parser.add_argument(
        "--report",
        type=str,
        help="Generate report from existing matched jobs JSON",
    )

    parser.add_argument(
        "--full-pipeline",
        action="store_true",
        help="Run complete pipeline (score + analyze + optimize + report)",
    )

    parser.add_argument(
        "--all-sources",
        action="store_true",
        help="Process all source files (jobs_*_latest.json) and generate separate reports",
    )

    parser.add_argument(
        "--no-skip-processed",
        action="store_true",
        help="Process all jobs, even if already tracked",
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show job tracker statistics",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint if available",
    )

    parser.add_argument(
        "--email",
        action="store_true",
        help="Force send email report (overrides config)",
    )

    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Skip email report (overrides config)",
    )

    parser.add_argument(
        "--failure-stats",
        action="store_true",
        help="Show detailed failure statistics",
    )

    parser.add_argument(
        "--retry-failed",
        type=str,
        choices=["scoring", "analysis", "optimization"],
        help="Retry failed jobs from specific stage",
    )

    parser.add_argument(
        "--retry-temp",
        type=float,
        help="Override temperature for retry (default: from .env)",
    )

    parser.add_argument(
        "--retry-tokens",
        type=int,
        help="Override max_tokens for retry (default: from .env)",
    )

    parser.add_argument(
        "--batch-queue",
        action="store_true",
        help="Enable batch queue mode for constant GPU load (default: from .env)",
    )

    parser.add_argument(
        "--no-batch-queue",
        action="store_true",
        help="Disable batch queue mode (use sequential processing)",
    )

    args = parser.parse_args()

    # Determine email setting
    email_override = None
    if args.email:
        email_override = True
    elif args.no_email:
        email_override = False

    # Determine batch queue setting
    batch_queue_override = None
    if args.batch_queue:
        batch_queue_override = True
    elif args.no_batch_queue:
        batch_queue_override = False

    try:
        pipeline = JobMatcherPipeline(enable_email=email_override, use_batch_queue=batch_queue_override)

        # Show stats if requested
        if args.stats:
            stats = pipeline.tracker.get_stats()
            print("\n[INFO] Job Tracker Statistics:")
            print(f"   Total jobs tracked: {stats['total_jobs']}")
            print(f"   Average score: {stats['avg_score']}")
            print(f"   High matches (≥80): {stats['high_matches']}")
            print(f"   Medium matches (70-79): {stats['medium_matches']}")
            print(f"   Low matches (<70): {stats['low_matches']}")
            print(f"   Reposted jobs: {stats['reposted_jobs']}")
            return

        # Show failure stats if requested
        if args.failure_stats:
            failure_stats = pipeline.failure_tracker.get_failure_stats()
            print("\n[WARNING] Failure Statistics:")
            print(f"   Total failures: {failure_stats['total_failures']}")

            if failure_stats['total_failures'] > 0:
                print(f"\n   By Stage:")
                for stage, count in failure_stats['by_stage'].items():
                    print(f"     - {stage}: {count} failures")

                print(f"\n   By Error Type:")
                for error_type, count in failure_stats['by_error_type'].items():
                    print(f"     - {error_type}: {count} failures")

                print(f"\n   Multiple Failures: {failure_stats['multiple_failures']} jobs")

                if failure_stats['top_failures']:
                    print(f"\n   Most Problematic Jobs:")
                    for i, failure in enumerate(failure_stats['top_failures'], 1):
                        print(f"     {i}. {failure['job_title']} ({failure['stage']}): {failure['failure_count']} attempts")
                        print(f"        URL: {failure['job_url']}")
            else:
                print("   No failures recorded!")
            return

        # Retry failed jobs if requested
        if args.retry_failed:
            stage = args.retry_failed
            print(f"\n{'=' * 80}")
            print(f"RETRYING FAILED JOBS - {stage.upper()} STAGE")
            print(f"{'=' * 80}")

            # Get failed jobs from tracker
            failed_records = pipeline.failure_tracker.get_failed_jobs(stage=stage)

            if not failed_records:
                print(f"\n[SUCCESS] No failed jobs found for {stage} stage!")
                return

            print(f"Found {len(failed_records)} failed jobs to retry")

            # Extract job data from records
            jobs_to_retry = [record['job_data'] for record in failed_records]

            # Apply retry configuration overrides
            if args.retry_temp:
                print(f"Using retry temperature: {args.retry_temp}")
                # Temporarily override in environment
                original_temp = os.getenv("LLAMA_TEMPERATURE")
                os.environ["LLAMA_TEMPERATURE"] = str(args.retry_temp)

            if args.retry_tokens:
                print(f"Using retry max_tokens: {args.retry_tokens}")
                original_tokens = os.getenv("LLAMA_MAX_TOKENS")
                os.environ["LLAMA_MAX_TOKENS"] = str(args.retry_tokens)

            # Load resume/requirements
            print("\nLoading resume and requirements...")
            if not pipeline.analyzer.load_all():
                print("[WARNING] Failed to load resume and requirements")
                return

            # Test connection
            print("Testing llama-server connection...")
            if not pipeline.client.test_connection():
                print("[WARNING] Failed to connect to llama-server")
                return

            print(f"\nRetrying {len(jobs_to_retry)} jobs...")

            # Retry based on stage
            if stage == "scoring":
                matched_jobs = pipeline.run_scoring_pass(jobs_to_retry, args.min_score)
                if matched_jobs:
                    output_file = pipeline.save_matched_jobs(matched_jobs)
                    pipeline.update_tracker(matched_jobs)
                    print(f"\n[SUCCESS] Successfully retried! {len(matched_jobs)} jobs matched")
                    print(f"   Saved to: {output_file}")

            elif stage == "analysis":
                analyzed_jobs = pipeline.run_analysis_pass(jobs_to_retry)
                if analyzed_jobs:
                    output_file = pipeline.save_matched_jobs(analyzed_jobs)
                    print(f"\n[SUCCESS] Successfully retried! {len(analyzed_jobs)} jobs analyzed")
                    print(f"   Saved to: {output_file}")

            elif stage == "optimization":
                optimized_jobs = pipeline.run_optimization_pass(jobs_to_retry)
                if optimized_jobs:
                    output_file = pipeline.save_matched_jobs(optimized_jobs)
                    print(f"\n[SUCCESS] Successfully retried! {len(optimized_jobs)} jobs optimized")
                    print(f"   Saved to: {output_file}")

            # Restore original environment variables
            if args.retry_temp and original_temp:
                os.environ["LLAMA_TEMPERATURE"] = original_temp
            if args.retry_tokens and original_tokens:
                os.environ["LLAMA_MAX_TOKENS"] = original_tokens

            # Mark successful retries as resolved
            successful_urls = {job.get("job_url") for job in (matched_jobs if stage == "scoring" else analyzed_jobs if stage == "analysis" else optimized_jobs) if job.get("match_score", 0) > 0 or stage != "scoring"}
            for job_url in successful_urls:
                pipeline.failure_tracker.mark_resolved(job_url, stage)

            print(f"\n[SUCCESS] Retry complete! Check failure stats to see remaining failures.")
            return

        # Generate report from existing matched jobs
        if args.report:
            print(f"Generating report from: {args.report}")
            jobs = pipeline.load_jobs(args.report)
            report_path = pipeline.generate_report(jobs)
            print(f"\nReport generated: {report_path}")
            return

        # Process all sources
        if args.all_sources:
            source_results = pipeline.process_all_sources(
                min_score=args.min_score,
                skip_processed=not args.no_skip_processed,
                resume_from_checkpoint=args.resume,
            )

            if source_results:
                # Send multi-source email if enabled
                pipeline.send_multi_source_email_report(source_results)

                print("\n" + "=" * 80)
                print("ALL SOURCES COMPLETE")
                print("=" * 80)
                print(f"Processed {len(source_results)} source(s):")
                for source, report_path, jobs in source_results:
                    print(f"\n  {source.upper()}:")
                    print(f"    Matches: {len(jobs)}")
                    print(f"    Report: {report_path}")
                print("=" * 80)
                print("\n[SUCCESS] All done! Open the reports in your browser.")
            else:
                print("\n[WARNING] No sources were processed successfully.")
            return

        # Run full pipeline (single source)
        if args.full_pipeline:
            report_path = pipeline.run_full_pipeline(
                args.input,
                min_score=args.min_score,
                skip_processed=not args.no_skip_processed,
                resume_from_checkpoint=args.resume,
            )

            if report_path:
                print("\n[SUCCESS] All done! Open the report in your browser.")
            return

        # Default: just run scoring pass
        pipeline.analyzer.load_all()
        jobs = pipeline.load_jobs(args.input)

        if not args.no_skip_processed:
            jobs = pipeline.filter_unprocessed_jobs(jobs)

        matched_jobs = pipeline.run_scoring_pass(jobs, args.min_score)

        if matched_jobs:
            pipeline.save_matched_jobs(matched_jobs)
            pipeline.update_tracker(matched_jobs)

    except KeyboardInterrupt:
        print("\n\n[WARNING] Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
