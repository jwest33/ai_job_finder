"""
Job Matcher Tools

Tools for AI-powered job matching, scoring, analysis, and optimization.
"""

import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .base import matcher_registry, BaseTool
from ..utils.response_formatter import format_success_response


class MatcherFullPipelineTool(BaseTool):
    """Run complete 3-pass matching pipeline"""

    def __init__(self):
        super().__init__("full_pipeline", "Run complete matching pipeline (score → analyze → optimize)")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        from ..utils.error_handler import NotFoundError
        params = self.validate_parameters(
            kwargs,
            required=[],
            optional=["input_file", "source", "min_score", "resume_checkpoint", "no_skip", "send_email"],
        )

        # Import dependencies
        try:
            import json
            import os
            from pathlib import Path
            from datetime import datetime
            from dotenv import load_dotenv
            from src.job_matcher import (
                JobTracker,
                LlamaClient,
                ResumeAnalyzer,
                MatchScorer,
                GapAnalyzer,
                ResumeOptimizer,
                ReportGenerator,
                CheckpointManager,
                FailureTracker,
                EmailService,
            )
            from src.utils.profile_manager import ProfilePaths
            load_dotenv()
        except ImportError as e:
            from ..utils.response_formatter import format_error_response
            return format_error_response(
                error=f"Failed to import matcher modules: {e}",
                error_type="ImportError",
                details={"suggestion": "Ensure src.job_matcher package is properly installed"},
            )

        # Get parameters
        source = params.get("source", "indeed")
        input_file = params.get("input_file")
        if not input_file:
            input_file = str(ProfilePaths().data_dir / f"jobs_{source}_latest.json")

        # Check if input file exists
        if not Path(input_file).exists():
            raise NotFoundError(
                message=f"Input file not found: {input_file}",
                details={
                    "input_file": input_file,
                    "source": source,
                    "suggestion": f"Run scraper.search first to generate jobs data",
                },
            )

        min_score = params.get("min_score", int(os.getenv("MIN_MATCH_SCORE", "70")))
        resume_checkpoint = params.get("resume_checkpoint", False)
        skip_processed = not params.get("no_skip", False)

        # Initialize all components
        profile_name = os.getenv("ACTIVE_PROFILE", "default")
        tracker = JobTracker()
        client = LlamaClient()
        analyzer = ResumeAnalyzer()
        checkpoint_manager = CheckpointManager()
        failure_tracker = FailureTracker()
        scorer = MatchScorer(client, analyzer, checkpoint_manager, failure_tracker)
        gap_analyzer = GapAnalyzer(client, analyzer, checkpoint_manager, failure_tracker)
        optimizer = ResumeOptimizer(client, analyzer, checkpoint_manager, failure_tracker)
        report_gen = ReportGenerator()
        email_service = EmailService(profile_name=profile_name)

        # Load resume and requirements
        if not analyzer.load_all():
            from ..utils.response_formatter import format_error_response
            return format_error_response(
                error="Failed to load resume and requirements",
                error_type="ConfigurationError",
                details={
                    "resume_path": str(ProfilePaths().resume_path),
                    "requirements_path": str(ProfilePaths().requirements_path),
                    "suggestion": "Check that resume.txt and requirements.yaml exist",
                },
            )

        # Test llama-server connection
        if not client.test_connection():
            from ..utils.response_formatter import format_error_response
            return format_error_response(
                error=f"Failed to connect to llama-server at {client.server_url}",
                error_type="ConnectionError",
                details={
                    "server_url": client.server_url,
                    "suggestion": "Ensure llama-server is running",
                },
            )

        # Load jobs
        with open(input_file, "r", encoding="utf-8") as f:
            jobs = json.load(f)

        # Filter unprocessed jobs if requested
        original_count = len(jobs)
        if skip_processed:
            unprocessed = []
            for job in jobs:
                if not tracker.is_processed(job.get("job_url", "")):
                    unprocessed.append(job)
            jobs = unprocessed
        skipped_count = original_count - len(jobs)

        if not jobs:
            from ..utils.response_formatter import format_error_response
            return format_error_response(
                error="No jobs to process",
                details={
                    "total_jobs_loaded": original_count,
                    "already_processed": skipped_count,
                    "suggestion": "All jobs have been processed. Use no_skip=true to reprocess",
                },
            )

        # Create checkpoint if resuming
        resuming = False
        if resume_checkpoint and checkpoint_manager.has_checkpoint(input_file):
            resuming = True

        if not resuming:
            checkpoint_manager.create_checkpoint(input_file, min_score)
            failure_tracker.reset()

        # PASS 1: Scoring
        if not resuming or not checkpoint_manager.is_stage_completed("scoring"):
            scored_jobs = scorer.score_jobs_batch(jobs, progress_callback=None)
            matched = [j for j in scored_jobs if j.get("match_score", 0) >= min_score]
            rejected = [j for j in scored_jobs if j.get("match_score", 0) < min_score]

            if not matched:
                checkpoint_manager.clear_checkpoint()
                from ..utils.response_formatter import format_error_response
                return format_error_response(
                    error=f"No jobs met minimum score threshold ({min_score})",
                    details={
                        "scored": len(scored_jobs),
                        "matched": 0,
                        "min_score": min_score,
                        "suggestion": "Try lowering min_score parameter",
                    },
                )

            # Save intermediate results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            matched_file = ProfilePaths().data_dir / f"jobs_{source}_matched_{timestamp}.json"
            matched_file.parent.mkdir(parents=True, exist_ok=True)
            with open(matched_file, "w", encoding="utf-8") as f:
                json.dump(matched, f, indent=2, ensure_ascii=False)

            checkpoint_manager.mark_stage_completed("scoring", len(matched))
        else:
            # Load from checkpoint
            matched_file = Path(checkpoint_manager.get_output_file("matched_jobs"))
            with open(matched_file, "r", encoding="utf-8") as f:
                matched = json.load(f)

        # PASS 2: Gap Analysis
        if not resuming or not checkpoint_manager.is_stage_completed("analysis"):
            analyzed = gap_analyzer.analyze_jobs_batch(matched, progress_callback=None)

            # Save updated results
            with open(matched_file, "w", encoding="utf-8") as f:
                json.dump(analyzed, f, indent=2, ensure_ascii=False)

            checkpoint_manager.mark_stage_completed("analysis")
        else:
            analyzed = matched

        # PASS 3: Resume Optimization
        if not resuming or not checkpoint_manager.is_stage_completed("optimization"):
            optimized = optimizer.optimize_jobs_batch(analyzed, progress_callback=None)

            # Save final results
            with open(matched_file, "w", encoding="utf-8") as f:
                json.dump(optimized, f, indent=2, ensure_ascii=False)

            checkpoint_manager.mark_stage_completed("optimization")
        else:
            optimized = analyzed

        # Update tracker
        for job in optimized:
            tracker.add_job(
                job_url=job.get("job_url", ""),
                job_title=job.get("title", "Unknown"),
                company=job.get("company", "Unknown"),
                location=job.get("location", "Unknown"),
                match_score=job.get("match_score", 0),
            )

        # Generate report
        report_title = f"Job Match Report - {source.title()} - {datetime.now().strftime('%B %d, %Y')}"
        report_path = report_gen.generate_report(optimized, report_title, source_file=str(matched_file), source=source)

        # Email integration
        email_sent = False
        send_email = params.get("send_email", True)  # Default to True for backward compatibility
        email_enabled = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
        if send_email and email_enabled and email_service.is_configured():
            email_min_matches = int(os.getenv("EMAIL_MIN_MATCHES", "1"))
            if len(optimized) >= email_min_matches:
                email_recipients_str = os.getenv("EMAIL_RECIPIENT", "")
                email_recipients = [e.strip() for e in email_recipients_str.split(',') if e.strip()]
                if email_recipients:
                    subject_prefix = os.getenv("EMAIL_SUBJECT_PREFIX", "[Job Matcher]")
                    for recipient in email_recipients:
                        email_service.send_report(recipient, optimized, report_path, subject_prefix)
                    email_sent = True

        # Clear checkpoint
        checkpoint_manager.clear_checkpoint()

        # Get failure stats
        failure_stats = failure_tracker.get_failure_stats()
        scoring_failures = scorer.get_failed_jobs()
        analysis_failures = gap_analyzer.get_failed_jobs()
        optimization_failures = optimizer.get_failed_jobs()

        # Build response
        result_data = {
            "input_file": input_file,
            "source": source,
            "min_score": min_score,
            "passes_completed": ["scoring", "gap_analysis", "resume_optimization"],
            "stats": {
                "total_jobs_loaded": original_count,
                "already_processed": skipped_count,
                "processed": len(jobs),
                "matched": len(optimized),
                "failed": {
                    "scoring": len(scoring_failures),
                    "gap_analysis": len(analysis_failures),
                    "resume_optimization": len(optimization_failures),
                    "total": failure_stats["total_failures"],
                },
            },
            "output_files": {
                "matched_jobs": str(matched_file),
                "report": str(report_path),
            },
            "email_sent": email_sent,
        }

        # Add sample top matches
        if optimized:
            result_data["sample_top_matches"] = [
                {
                    "title": job.get("title"),
                    "company": job.get("company"),
                    "score": job.get("match_score"),
                    "strengths": job.get("strengths", [])[:3],
                    "gaps": job.get("gaps", [])[:3],
                    "top_keywords": job.get("keywords", [])[:3],
                }
                for job in sorted(optimized, key=lambda x: x.get("match_score", 0), reverse=True)[:5]
            ]

        message = f"Pipeline complete: {len(optimized)} matches found, report generated"
        if failure_stats["total_failures"] > 0:
            message += f" ({failure_stats['total_failures']} jobs failed)"

        return format_success_response(data=result_data, message=message)


class MatcherScoreTool(BaseTool):
    """Pass 1: Score jobs only"""

    def __init__(self):
        super().__init__("score", "Score jobs against resume (Pass 1)")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        from ..utils.error_handler import NotFoundError
        params = self.validate_parameters(
            kwargs,
            required=[],
            optional=["input_file", "min_score", "source"],
        )

        # Import matcher dependencies
        try:
            import json
            from pathlib import Path
            from src.job_matcher import JobTracker, LlamaClient, ResumeAnalyzer, MatchScorer, CheckpointManager, FailureTracker
            from src.utils.profile_manager import ProfilePaths
        except ImportError as e:
            from ..utils.response_formatter import format_error_response
            return format_error_response(
                error=f"Failed to import matcher modules: {e}",
                error_type="ImportError",
                details={"suggestion": "Ensure src.job_matcher package is properly installed"},
            )

        # Get input file (default to source-specific latest file)
        source = params.get("source", "indeed")
        input_file = params.get("input_file")

        if not input_file:
            # Default to latest file from specified source
            input_file = str(ProfilePaths().data_dir / f"jobs_{source}_latest.json")

        # Check if input file exists
        if not Path(input_file).exists():
            raise NotFoundError(
                message=f"Input file not found: {input_file}",
                details={
                    "input_file": input_file,
                    "source": source,
                    "suggestion": f"Run scraper.search first to generate jobs data, or specify a different input_file",
                },
            )

        # Get minimum score (default to config)
        import os
        from dotenv import load_dotenv
        load_dotenv()
        min_score = params.get("min_score", int(os.getenv("MIN_MATCH_SCORE", "70")))

        # Initialize components
        tracker = JobTracker()
        client = LlamaClient()
        analyzer = ResumeAnalyzer()
        checkpoint_manager = CheckpointManager()
        failure_tracker = FailureTracker()
        scorer = MatchScorer(client, analyzer, checkpoint_manager, failure_tracker)

        # Load resume and requirements
        if not analyzer.load_all():
            from ..utils.response_formatter import format_error_response
            return format_error_response(
                error="Failed to load resume and requirements",
                error_type="ConfigurationError",
                details={
                    "resume_path": str(ProfilePaths().resume_path),
                    "requirements_path": str(ProfilePaths().requirements_path),
                    "suggestion": "Check that resume.txt and requirements.yaml exist in your profile templates directory",
                },
            )

        # Test llama-server connection
        if not client.test_connection():
            from ..utils.response_formatter import format_error_response
            return format_error_response(
                error=f"Failed to connect to llama-server at {client.server_url}",
                error_type="ConnectionError",
                details={
                    "server_url": client.server_url,
                    "suggestion": "Ensure llama-server is running on the configured port",
                },
            )

        # Load jobs
        with open(input_file, "r", encoding="utf-8") as f:
            jobs = json.load(f)

        # Filter unprocessed jobs
        unprocessed = []
        for job in jobs:
            job_url = job.get("job_url", "")
            if not tracker.is_processed(job_url):
                unprocessed.append(job)

        skipped_count = len(jobs) - len(unprocessed)

        # Score jobs
        scored_jobs = scorer.score_jobs_batch(unprocessed, progress_callback=None)

        # Filter by minimum score
        matched = []
        rejected = []
        for job in scored_jobs:
            if job.get("match_score", 0) >= min_score:
                matched.append(job)
            else:
                rejected.append(job)

        # Get additional stats
        title_rejected = scorer.get_rejected_jobs()
        failed_jobs = scorer.get_failed_jobs()

        # Save matched jobs
        if matched:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = ProfilePaths().data_dir / f"jobs_{source}_matched_{timestamp}.json"

            # Ensure directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(matched, f, indent=2, ensure_ascii=False)

            # Update tracker
            for job in matched:
                tracker.add_job(
                    job_url=job.get("job_url", ""),
                    job_title=job.get("title", "Unknown"),
                    company=job.get("company", "Unknown"),
                    location=job.get("location", "Unknown"),
                    match_score=job.get("match_score", 0),
                )
        else:
            output_file = None

        # Build response
        result_data = {
            "input_file": input_file,
            "source": source,
            "min_score": min_score,
            "stats": {
                "total_jobs_loaded": len(jobs),
                "already_processed": skipped_count,
                "scored": len(scored_jobs),
                "matched": len(matched),
                "rejected": len(rejected),
                "title_filtered": len(title_rejected),
                "failed": len(failed_jobs),
            },
            "output_file": str(output_file) if output_file else None,
        }

        if matched:
            # Add sample matches (top 5)
            result_data["sample_matches"] = [
                {
                    "title": job.get("title"),
                    "company": job.get("company"),
                    "score": job.get("match_score"),
                    "reasoning": job.get("reasoning", "")[:150] + "..." if len(job.get("reasoning", "")) > 150 else job.get("reasoning", ""),
                }
                for job in sorted(matched, key=lambda x: x.get("match_score", 0), reverse=True)[:5]
            ]

        message = f"Scoring complete: {len(matched)} matches found (score >= {min_score})"
        if failed_jobs:
            message += f", {len(failed_jobs)} jobs failed"

        return format_success_response(data=result_data, message=message)


class MatcherRetryFailedTool(BaseTool):
    """Retry failed jobs with configuration overrides"""

    def __init__(self):
        super().__init__("retry_failed", "Retry failed jobs with adjusted settings")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        params = self.validate_parameters(
            kwargs,
            required=["stage"],
            optional=["retry_temp", "retry_tokens"],
        )

        # Import dependencies
        try:
            import json
            import os
            from pathlib import Path
            from datetime import datetime
            from dotenv import load_dotenv
            from src.job_matcher import (
                JobTracker,
                LlamaClient,
                ResumeAnalyzer,
                MatchScorer,
                GapAnalyzer,
                ResumeOptimizer,
                CheckpointManager,
                FailureTracker,
            )
            from src.utils.profile_manager import ProfilePaths
            load_dotenv()
        except ImportError as e:
            from ..utils.response_formatter import format_error_response
            return format_error_response(
                error=f"Failed to import matcher modules: {e}",
                error_type="ImportError",
                details={"suggestion": "Ensure src.job_matcher package is properly installed"},
            )

        # Get parameters
        stage = params["stage"]
        retry_temp = params.get("retry_temp")
        retry_tokens = params.get("retry_tokens")

        # Validate stage
        valid_stages = ["scoring", "analysis", "optimization"]
        if stage not in valid_stages:
            from ..utils.response_formatter import format_error_response
            return format_error_response(
                error=f"Invalid stage: {stage}",
                error_type="ValidationError",
                details={
                    "stage": stage,
                    "valid_stages": valid_stages,
                    "suggestion": f"Use one of: {', '.join(valid_stages)}",
                },
            )

        # Initialize components
        tracker = JobTracker()
        client = LlamaClient()
        analyzer = ResumeAnalyzer()
        checkpoint_manager = CheckpointManager()
        failure_tracker = FailureTracker()

        # Get failed jobs for this stage
        failed_records = failure_tracker.get_failed_jobs(stage=stage)

        if not failed_records:
            return format_success_response(
                data={
                    "stage": stage,
                    "total_failed_jobs": 0,
                    "message": f"No failed jobs found for {stage} stage",
                },
                message=f"No failures to retry for {stage} stage",
            )

        jobs_to_retry = [record['job_data'] for record in failed_records]

        # Apply temporary config overrides
        original_temp = os.getenv("LLAMA_TEMPERATURE")
        original_tokens = os.getenv("LLAMA_MAX_TOKENS")

        if retry_temp:
            os.environ["LLAMA_TEMPERATURE"] = str(retry_temp)
        if retry_tokens:
            os.environ["LLAMA_MAX_TOKENS"] = str(retry_tokens)

        # Load resume and requirements
        if not analyzer.load_all():
            from ..utils.response_formatter import format_error_response
            return format_error_response(
                error="Failed to load resume and requirements",
                error_type="ConfigurationError",
                details={
                    "resume_path": str(ProfilePaths().resume_path),
                    "requirements_path": str(ProfilePaths().requirements_path),
                    "suggestion": "Check that resume.txt and requirements.yaml exist",
                },
            )

        # Test llama-server connection
        if not client.test_connection():
            from ..utils.response_formatter import format_error_response
            return format_error_response(
                error=f"Failed to connect to llama-server at {client.server_url}",
                error_type="ConnectionError",
                details={
                    "server_url": client.server_url,
                    "suggestion": "Ensure llama-server is running",
                },
            )

        # Retry based on stage
        retry_succeeded = []
        retry_failed = []

        if stage == "scoring":
            scorer = MatchScorer(client, analyzer, checkpoint_manager, failure_tracker)
            scored_jobs = scorer.score_jobs_batch(jobs_to_retry, progress_callback=None)

            for job in scored_jobs:
                if job.get("match_score") is not None:
                    retry_succeeded.append(job)
                else:
                    retry_failed.append(job)

        elif stage == "analysis":
            gap_analyzer = GapAnalyzer(client, analyzer, checkpoint_manager, failure_tracker)
            analyzed_jobs = gap_analyzer.analyze_jobs_batch(jobs_to_retry, progress_callback=None)

            for job in analyzed_jobs:
                if job.get("strengths") is not None:
                    retry_succeeded.append(job)
                else:
                    retry_failed.append(job)

        elif stage == "optimization":
            optimizer = ResumeOptimizer(client, analyzer, checkpoint_manager, failure_tracker)
            optimized_jobs = optimizer.optimize_jobs_batch(jobs_to_retry, progress_callback=None)

            for job in optimized_jobs:
                if job.get("keywords") is not None:
                    retry_succeeded.append(job)
                else:
                    retry_failed.append(job)

        # Restore original config
        if retry_temp and original_temp:
            os.environ["LLAMA_TEMPERATURE"] = original_temp
        if retry_tokens and original_tokens:
            os.environ["LLAMA_MAX_TOKENS"] = original_tokens

        # Save successful retries
        output_file = None
        if retry_succeeded:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = ProfilePaths().data_dir / f"jobs_retry_{stage}_{timestamp}.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(retry_succeeded, f, indent=2, ensure_ascii=False)

            # Mark successful retries as resolved
            for job in retry_succeeded:
                job_url = job.get("job_url", "")
                if job_url:
                    failure_tracker.mark_resolved(job_url, stage)

            # Update tracker for scoring stage
            if stage == "scoring":
                for job in retry_succeeded:
                    tracker.add_job(
                        job_url=job.get("job_url", ""),
                        job_title=job.get("title", "Unknown"),
                        company=job.get("company", "Unknown"),
                        location=job.get("location", "Unknown"),
                        match_score=job.get("match_score", 0),
                    )

        # Get remaining failures
        remaining_failures = failure_tracker.get_failed_jobs(stage=stage)

        # Build response
        result_data = {
            "stage": stage,
            "retry_config": {
                "temperature": retry_temp or original_temp,
                "max_tokens": retry_tokens or original_tokens,
            },
            "stats": {
                "total_failed_jobs": len(failed_records),
                "retry_attempted": len(jobs_to_retry),
                "retry_succeeded": len(retry_succeeded),
                "retry_failed": len(retry_failed),
                "resolved_jobs": len(retry_succeeded),
                "remaining_failures": len(remaining_failures),
            },
            "output_file": str(output_file) if output_file else None,
        }

        if remaining_failures:
            result_data["remaining_failures_note"] = f"{len(remaining_failures)} jobs still failing after retry"

        message = f"Retry complete: {len(retry_succeeded)} of {len(jobs_to_retry)} jobs succeeded"
        if remaining_failures:
            message += f", {len(remaining_failures)} still failing"

        return format_success_response(data=result_data, message=message)


# Register tools
matcher_registry.register("full_pipeline", MatcherFullPipelineTool())
matcher_registry.register("score", MatcherScoreTool())
matcher_registry.register("retry_failed", MatcherRetryFailedTool())


async def execute(tool_action: str, parameters: Dict[str, Any]) -> Any:
    """Execute a matcher tool"""
    tool = matcher_registry.get(tool_action)
    if not tool:
        raise ValueError(f"Unknown matcher tool: {tool_action}")
    return await tool.execute(**parameters)
