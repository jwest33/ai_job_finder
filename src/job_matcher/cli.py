"""
Job Matcher CLI Commands

Commands for running job matching pipeline, scoring, analysis, and optimization.
"""

import sys
from pathlib import Path

import click

# Add parent directory to path for cli_utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.profile_manager import ProfilePaths
from src.cli.utils import (
    print_header,
    print_section,
    print_success,
    print_error,
    print_info,
    print_key_value_table,
    confirm,
    handle_error,
    cli_state,
)


@click.group(name="matcher")
def matcher_group():
    """Job matching and analysis commands"""
    pass


@matcher_group.command(name="full-pipeline")
@click.option("--input", "-i", "input_file", default=None, help="Input jobs JSON file")
@click.option("--source", "-s", type=click.Choice(['indeed', 'glassdoor', 'linkedin', 'ziprecruiter'], case_sensitive=False), help="Filter by job source")
@click.option("--min-score", type=int, help="Minimum match score (default: from .env)")
@click.option("--resume", "resume_checkpoint", is_flag=True, help="Resume from checkpoint")
@click.option("--no-skip", is_flag=True, help="Process all jobs (ignore tracker)")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmations")
@click.option("--email", is_flag=True, help="Force send email after completion (overrides config)")
@click.option("--no-email", is_flag=True, help="Disable email after completion (overrides config)")
def full_pipeline(input_file, source, min_score, resume_checkpoint, no_skip, yes, email, no_email):
    """Run complete matching pipeline (score + analyze + optimize + report)

    If no input file or source is specified, processes ALL available sources.

    Examples:
        python cli.py matcher full-pipeline                    # All sources
        python cli.py matcher full-pipeline -s glassdoor       # Single source
        python cli.py matcher full-pipeline -i data/jobs.json  # Specific file
        python cli.py matcher full-pipeline --email            # All sources + email
    """

    print_header("Job Matcher - Full Pipeline")

    try:
        # Import JobMatcherPipeline from the main script (job_matcher.py)
        import importlib.util
        import os

        script_path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "job_matcher.py")
        spec = importlib.util.spec_from_file_location("job_matcher_script", script_path)
        job_matcher_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(job_matcher_module)

        JobMatcherPipeline = job_matcher_module.JobMatcherPipeline

        # Determine email override setting
        email_override = None
        if email:
            email_override = True
        elif no_email:
            email_override = False

        # MULTI-SOURCE MODE: No input file and no source specified
        if not input_file and not source:
            print_info("No source specified, finding all available sources...")

            available_sources = find_available_source_files()

            if not available_sources:
                print_error("No source files found in data/ directory")
                print_info("Run scraper first to collect jobs:")
                print_info("  python cli.py scraper search -s indeed")
                print_info("  python cli.py scraper search -s glassdoor")
                sys.exit(1)

            print_success(f"Found sources: {', '.join(available_sources.keys())}")

            # Process each source through full pipeline
            generated_reports = []
            total_matches = 0

            for src_name, source_file in available_sources.items():
                print_section(f"Processing {src_name.title()}")
                print_info(f"Input file: {source_file}")

                # Disable auto-email in multi-source mode unless explicitly requested
                pipeline = JobMatcherPipeline(enable_email=email_override if email_override is not None else False)
                pipeline.job_source = src_name

                try:
                    report_path = pipeline.run_full_pipeline(
                        input_file=str(source_file),
                        min_score=min_score,
                        skip_processed=not no_skip,
                        resume_from_checkpoint=resume_checkpoint,
                    )

                    if report_path:
                        print_success(f"✓ {src_name.title()} complete: {report_path}")
                        generated_reports.append(report_path)

                        # Count matches from the report path name or assume success
                        total_matches += 1
                    else:
                        print_info(f"  No matches found for {src_name}")

                except Exception as e:
                    print_error(f"  Failed to process {src_name}: {e}")
                    continue

            # Summary
            print_section("Summary")
            if generated_reports:
                print_success(f"Processed {len(generated_reports)} source(s) successfully:")
                for rp in generated_reports:
                    print_info(f"  • {rp}")
            else:
                print_info("No matches found across all sources")

            # Send email if requested
            if email and generated_reports:
                print_info("\nSending email with all reports...")
                from job_matcher.cli_email import send_email as email_send_func
                from click.testing import CliRunner

                runner = CliRunner()
                result = runner.invoke(email_send_func, [], catch_exceptions=False)

                if result.exit_code == 0:
                    print_success("Email sent successfully")
                else:
                    print_error("Failed to send email")

        # SINGLE-SOURCE MODE: Source or input file specified
        else:
            # Resolve input file based on source
            if source and not input_file:
                input_file = str(ProfilePaths().data_dir / f"jobs_{source.lower()}_latest.json")
                print_info(f"Using source file: {input_file}")
            elif not input_file:
                input_file = str(ProfilePaths().data_dir / "jobs_indeed_latest.json")

            # Validate file exists
            if not Path(input_file).exists():
                print_error(f"Input file not found: {input_file}")
                if source:
                    print_info(f"No jobs found for source '{source}'. Run scraper first:")
                    print_info(f"  python cli.py scraper search -s {source}")
                sys.exit(1)

            pipeline = JobMatcherPipeline(enable_email=email_override)

            # Detect source from filename if not specified
            if source:
                pipeline.job_source = source.lower()
            else:
                pipeline.job_source = pipeline.detect_source_from_filename(input_file)

            print_info(f"Processing source: {pipeline.job_source}")

            # Run pipeline
            report_path = pipeline.run_full_pipeline(
                input_file=input_file,
                min_score=min_score,
                skip_processed=not no_skip,
                resume_from_checkpoint=resume_checkpoint,
            )

            if report_path:
                print_success(f"\nPipeline complete! Report: {report_path}")

                # Send email if requested
                if email:
                    print_info("\nSending email with report...")
                    from job_matcher.cli_email import send_email as email_send_func
                    from click.testing import CliRunner

                    runner = CliRunner()
                    result = runner.invoke(email_send_func, [report_path], catch_exceptions=False)

                    if result.exit_code == 0:
                        print_success("Email sent successfully")
                    else:
                        print_error("Failed to send email")
            else:
                print_info("No matches found")

    except KeyboardInterrupt:
        print_error("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)
        sys.exit(1)


@matcher_group.command(name="score")
@click.option("--input", "-i", "input_file", default=None, help="Input jobs JSON file")
@click.option("--source", "-s", type=click.Choice(['indeed', 'glassdoor', 'linkedin', 'ziprecruiter'], case_sensitive=False), help="Filter by job source")
@click.option("--min-score", type=int, help="Minimum match score (default: 70)")
@click.option("--no-skip", is_flag=True, help="Process all jobs (ignore tracker)")
def score_jobs(input_file, source, min_score, no_skip):
    """Score jobs against resume (Pass 1 only)"""

    print_header("Job Matcher - Scoring")

    try:
        # Resolve input file based on source
        if source and not input_file:
            input_file = str(ProfilePaths().data_dir / f"jobs_{source.lower()}_latest.json")
            print_info(f"Using source file: {input_file}")
        elif not input_file:
            input_file = str(ProfilePaths().data_dir / "jobs_indeed_latest.json")

        # Validate file exists
        if not Path(input_file).exists():
            print_error(f"Input file not found: {input_file}")
            if source:
                print_info(f"No jobs found for source '{source}'. Run scraper first:")
                print_info(f"  python cli.py scraper search -s {source}")
            sys.exit(1)

        # Import JobMatcherPipeline from the main script
        import importlib.util
        import os

        script_path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "job_matcher.py")
        spec = importlib.util.spec_from_file_location("job_matcher_script", script_path)
        job_matcher_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(job_matcher_module)

        JobMatcherPipeline = job_matcher_module.JobMatcherPipeline
        pipeline = JobMatcherPipeline(enable_checkpoints=False)

        # Load resume
        pipeline.analyzer.load_all()

        # Load and filter jobs
        jobs = pipeline.load_jobs(input_file)

        if not no_skip:
            jobs = pipeline.filter_unprocessed_jobs(jobs)

        if not jobs:
            print_info("No jobs to process")
            return

        # Score jobs
        matched_jobs = pipeline.run_scoring_pass(jobs, min_score)

        if matched_jobs:
            output_file = pipeline.save_matched_jobs(matched_jobs)
            pipeline.update_tracker(matched_jobs)

            print_success(f"\nFound {len(matched_jobs)} matches")
            print_info(f"Saved to: {output_file}")
        else:
            print_info("No matches found")

    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)
        sys.exit(1)


def find_latest_matched_jobs(source=None):
    """Find most recent matched jobs file by timestamp

    Args:
        source: Optional source to filter by (e.g., 'indeed', 'glassdoor')

    Returns:
        Path to latest matched jobs file, or None if not found
    """
    data_dir = ProfilePaths().data_dir

    if not data_dir.exists():
        return None

    # Find all matched jobs files
    if source:
        # Filter by source
        matched_files = list(data_dir.glob(f"jobs_{source.lower()}_matched_*.json"))
    else:
        # Find all jobs_*_matched_*.json files (new naming pattern)
        matched_files = list(data_dir.glob("jobs_*_matched_*.json"))

        # Also check for legacy naming pattern for backward compatibility
        if not matched_files:
            matched_files = list(data_dir.glob("jobs_matched_*.json"))

    if not matched_files:
        return None

    # Sort by modification time (most recent first)
    matched_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    return matched_files[0]


def find_latest_matched_jobs_by_source():
    """Find most recent matched jobs file for each source

    Returns:
        Dict mapping source name to file path
    """
    data_dir = ProfilePaths().data_dir
    if not data_dir.exists():
        return {}

    sources = {}
    for source in ["indeed", "glassdoor", "linkedin", "ziprecruiter"]:
        pattern = f"jobs_{source}_matched_*.json"
        matched_files = list(data_dir.glob(pattern))

        if matched_files:
            matched_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            sources[source] = matched_files[0]

    return sources


def find_available_source_files():
    """Find all available jobs_*_latest.json files

    Returns:
        Dict mapping source name to file path
    """
    data_dir = ProfilePaths().data_dir
    if not data_dir.exists():
        return {}

    sources = {}
    for source in ["indeed", "glassdoor", "linkedin", "ziprecruiter"]:
        source_file = data_dir / f"jobs_{source}_latest.json"
        if source_file.exists():
            sources[source] = source_file

    return sources


@matcher_group.command(name="report")
@click.argument("jobs_file", required=False)
@click.option("--source", "-s", type=click.Choice(['indeed', 'glassdoor', 'linkedin', 'ziprecruiter'], case_sensitive=False), help="Filter by job source")
@click.option("--title", help="Report title")
@click.option("--email", is_flag=True, help="Send report via email after generation")
def generate_report(jobs_file, source, title, email):
    """Generate HTML report from matched jobs JSON

    If no file is specified, generates reports for ALL sources with matched jobs.
    Use --source to generate a report for only one specific source.

    Examples:
        python cli.py matcher report                         # All sources
        python cli.py matcher report -s glassdoor            # Single source
        python cli.py matcher report data/jobs_matched.json  # Specific file
        python cli.py matcher report --email                 # All sources + email
    """

    print_header("Generate Report")

    try:
        # Import JobMatcherPipeline from the main script
        import importlib.util
        import os

        script_path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "job_matcher.py")
        spec = importlib.util.spec_from_file_location("job_matcher_script", script_path)
        job_matcher_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(job_matcher_module)

        JobMatcherPipeline = job_matcher_module.JobMatcherPipeline

        # MULTI-SOURCE MODE: No file specified and no source filter
        if not jobs_file and not source:
            print_info("No file specified, finding all available sources...")

            available_sources = find_latest_matched_jobs_by_source()

            if not available_sources:
                print_error("No matched jobs found in data/ directory")
                print_info("Run 'python cli.py match' first to generate matched jobs")
                sys.exit(1)

            print_success(f"Found matched jobs for: {', '.join(available_sources.keys())}")

            # Generate report for each source
            generated_reports = []

            for src_name, jobs_path in available_sources.items():
                print_section(f"Generating {src_name.title()} Report")
                print_info(f"Loading jobs from: {jobs_path}")

                pipeline = JobMatcherPipeline(enable_checkpoints=False)
                pipeline.job_source = src_name

                jobs = pipeline.load_jobs(str(jobs_path))
                report_path = pipeline.generate_report(jobs, title, source_file=str(jobs_path))

                print_success(f"✓ {src_name.title()} report: {report_path}")
                generated_reports.append(report_path)

            # Summary
            print_section("Summary")
            print_success(f"Generated {len(generated_reports)} reports:")
            for rp in generated_reports:
                print_info(f"  • {rp}")

            # Send email if requested
            if email:
                print_info("\nSending all reports via email...")
                from job_matcher.cli_email import send_email as email_send_func
                from click.testing import CliRunner

                runner = CliRunner()
                result = runner.invoke(email_send_func, [], catch_exceptions=False)

                if result.exit_code == 0:
                    print_success("Email sent successfully")
                else:
                    print_error("Failed to send email")

        # SINGLE-SOURCE MODE: Source filter specified or specific file provided
        else:
            # Auto-detect latest matched jobs if no file provided
            if not jobs_file:
                print_info(f"Finding latest matched jobs for source: {source}...")

                latest = find_latest_matched_jobs(source=source)

                if not latest:
                    print_error(f"No matched jobs found for source '{source}' in data/ directory")
                    print_info(f"Run 'python cli.py match -s {source}' first to generate matched jobs")
                    sys.exit(1)

                jobs_file = str(latest)
                print_success(f"Found latest matched jobs: {jobs_file}")

            # Validate file exists
            if not Path(jobs_file).exists():
                print_error(f"Jobs file not found: {jobs_file}")
                sys.exit(1)

            pipeline = JobMatcherPipeline(enable_checkpoints=False)

            # Detect and set source from jobs file
            pipeline.job_source = pipeline.detect_source_from_filename(jobs_file)
            print_info(f"Detected source: {pipeline.job_source}")

            jobs = pipeline.load_jobs(jobs_file)
            report_path = pipeline.generate_report(jobs, title, source_file=jobs_file)

            print_success(f"Report generated: {report_path}")

            # Send email if requested
            if email:
                print_info("\nSending report via email...")
                from job_matcher.cli_email import send_email as email_send_func
                from click.testing import CliRunner

                runner = CliRunner()
                result = runner.invoke(email_send_func, [report_path], catch_exceptions=False)

                if result.exit_code == 0:
                    print_success("Email sent successfully")
                else:
                    print_error("Failed to send email")

    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)
        sys.exit(1)


@matcher_group.command(name="config")
def show_config():
    """Show current matcher configuration"""
    import os

    print_header("Matcher Configuration")

    config = {
        "Resume Path": os.getenv("RESUME_PATH", "templates/resume.txt"),
        "Requirements Path": os.getenv("REQUIREMENTS_PATH", "templates/requirements.yaml"),
        "Min Score": os.getenv("MIN_MATCH_SCORE", "70"),
        "Match Threads": os.getenv("MATCH_THREADS", "4"),
        "llama-server URL": os.getenv("LLAMA_SERVER_URL", "http://localhost:8080"),
        "Report Output Dir": os.getenv("REPORT_OUTPUT_DIR", "reports/"),
        "Job Tracker DB": os.getenv("JOB_TRACKER_DB", "job_tracker.db"),
    }

    print_key_value_table(config, title="Configuration")


@matcher_group.command(name="test-llama")
def test_llama_connection():
    """Test llama-server connection"""

    print_header("Testing llama-server")

    try:
        from job_matcher.llama_client import LlamaClient

        client = LlamaClient()

        print_info(f"Connecting to: {client.server_url}")

        if client.test_connection():
            print_success("Connection successful!")
        else:
            print_error("Connection failed")
            sys.exit(1)

    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)
        sys.exit(1)


@matcher_group.command(name="failure-stats")
def show_failure_stats():
    """Show detailed failure statistics from job processing"""

    print_header("Failure Statistics")

    try:
        # Import JobMatcherPipeline to access failure tracker
        import importlib.util
        import os

        script_path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "job_matcher.py")
        spec = importlib.util.spec_from_file_location("job_matcher_script", script_path)
        job_matcher_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(job_matcher_module)

        JobMatcherPipeline = job_matcher_module.JobMatcherPipeline
        pipeline = JobMatcherPipeline(enable_checkpoints=False)

        failure_stats = pipeline.failure_tracker.get_failure_stats()

        print_section("Overall Statistics")
        print_info(f"Total failures: {failure_stats['total_failures']}")

        if failure_stats['total_failures'] == 0:
            print_success("No failures recorded!")
            return

        print_section("Failures by Stage")
        for stage, count in failure_stats['by_stage'].items():
            print_info(f"  {stage}: {count} failures")

        print_section("Failures by Error Type")
        for error_type, count in failure_stats['by_error_type'].items():
            print_info(f"  {error_type}: {count} failures")

        print_section("Additional Info")
        print_info(f"Jobs with multiple failures: {failure_stats['multiple_failures']}")

        if failure_stats['top_failures']:
            print_section("Most Problematic Jobs")
            for i, failure in enumerate(failure_stats['top_failures'], 1):
                print_info(f"{i}. {failure['job_title']} ({failure['stage']})")
                print_info(f"   Failure count: {failure['failure_count']}")
                print_info(f"   URL: {failure['job_url']}")

    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)
        sys.exit(1)


@matcher_group.command(name="retry-failed")
@click.argument("stage", type=click.Choice(['scoring', 'analysis', 'optimization'], case_sensitive=False))
@click.option("--temp", type=float, help="Override AI temperature for retry")
@click.option("--tokens", type=int, help="Override max tokens for retry")
@click.option("--min-score", type=int, help="Minimum match score (for scoring stage)")
def retry_failed_jobs(stage, temp, tokens, min_score):
    """Retry failed jobs from specific stage

    STAGE: scoring, analysis, or optimization

    Examples:
        python cli.py matcher retry-failed scoring
        python cli.py matcher retry-failed analysis --temp 0.7
        python cli.py matcher retry-failed optimization --tokens 4096
    """

    print_header(f"Retry Failed Jobs - {stage.title()} Stage")

    try:
        # Import JobMatcherPipeline
        import importlib.util
        import os

        script_path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "job_matcher.py")
        spec = importlib.util.spec_from_file_location("job_matcher_script", script_path)
        job_matcher_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(job_matcher_module)

        JobMatcherPipeline = job_matcher_module.JobMatcherPipeline
        pipeline = JobMatcherPipeline(enable_checkpoints=False)

        # Get failed jobs from tracker
        print_section("Loading Failed Jobs")
        failed_records = pipeline.failure_tracker.get_failed_jobs(stage=stage)

        if not failed_records:
            print_success(f"No failed jobs found for {stage} stage!")
            return

        print_info(f"Found {len(failed_records)} failed jobs to retry")

        # Extract job data
        jobs_to_retry = [record['job_data'] for record in failed_records]

        # Apply retry configuration overrides
        original_temp = os.getenv("LLAMA_TEMPERATURE")
        original_tokens = os.getenv("LLAMA_MAX_TOKENS")

        if temp:
            print_info(f"Using retry temperature: {temp}")
            os.environ["LLAMA_TEMPERATURE"] = str(temp)

        if tokens:
            print_info(f"Using retry max_tokens: {tokens}")
            os.environ["LLAMA_MAX_TOKENS"] = str(tokens)

        # Load resume/requirements
        print_section("Initializing")
        print_info("Loading resume and requirements...")
        if not pipeline.analyzer.load_all():
            print_error("Failed to load resume and requirements")
            sys.exit(1)

        print_info("Testing llama-server connection...")
        if not pipeline.client.test_connection():
            print_error("Failed to connect to llama-server")
            sys.exit(1)

        print_success("Ready to retry")

        # Retry based on stage
        print_section(f"Retrying {len(jobs_to_retry)} Jobs")

        if stage == "scoring":
            matched_jobs = pipeline.run_scoring_pass(jobs_to_retry, min_score)
            if matched_jobs:
                output_file = pipeline.save_matched_jobs(matched_jobs)
                pipeline.update_tracker(matched_jobs)
                print_success(f"Successfully retried! {len(matched_jobs)} jobs matched")
                print_info(f"Saved to: {output_file}")

                # Mark successful as resolved
                for job in matched_jobs:
                    if job.get("match_score", 0) > 0:
                        pipeline.failure_tracker.mark_resolved(job.get("job_url"), stage)

        elif stage == "analysis":
            analyzed_jobs = pipeline.run_analysis_pass(jobs_to_retry)
            if analyzed_jobs:
                output_file = pipeline.save_matched_jobs(analyzed_jobs)
                print_success(f"Successfully retried! {len(analyzed_jobs)} jobs analyzed")
                print_info(f"Saved to: {output_file}")

                # Mark all as resolved (analysis doesn't fail on content)
                for job in analyzed_jobs:
                    pipeline.failure_tracker.mark_resolved(job.get("job_url"), stage)

        elif stage == "optimization":
            optimized_jobs = pipeline.run_optimization_pass(jobs_to_retry)
            if optimized_jobs:
                output_file = pipeline.save_matched_jobs(optimized_jobs)
                print_success(f"Successfully retried! {len(optimized_jobs)} jobs optimized")
                print_info(f"Saved to: {output_file}")

                # Mark all as resolved
                for job in optimized_jobs:
                    pipeline.failure_tracker.mark_resolved(job.get("job_url"), stage)

        # Restore original environment variables
        if temp and original_temp:
            os.environ["LLAMA_TEMPERATURE"] = original_temp
        if tokens and original_tokens:
            os.environ["LLAMA_MAX_TOKENS"] = original_tokens

        print_success("\nRetry complete! Use 'python cli.py matcher failure-stats' to check remaining failures.")

    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)
        sys.exit(1)
