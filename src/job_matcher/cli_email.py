"""
Email CLI Commands

Commands for configuring and testing email delivery.
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
    prompt_text,
    handle_error,
    cli_state,
)


@click.group(name="email")
def email_group():
    """Email configuration and delivery commands"""
    pass


@email_group.command(name="setup")
def setup_email():
    """Run interactive email setup wizard"""

    print_header("Email Setup Wizard")

    print_info("Launching email setup wizard...")
    print_info("This will guide you through Gmail OAuth2 configuration\n")

    try:
        import subprocess
        result = subprocess.run([sys.executable, "setup_email.py"])
        sys.exit(result.returncode)

    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)
        sys.exit(1)


@email_group.command(name="test")
@click.option("--recipient", help="Email recipient (default: from .env)")
def test_email(recipient):
    """Test email delivery"""

    print_header("Email Test")

    try:
        import os
        from job_matcher.email_service import EmailService

        if not recipient:
            recipient = os.getenv("EMAIL_RECIPIENT", "")

        if not recipient:
            print_error("No recipient specified. Use --recipient or set EMAIL_RECIPIENT in .env")
            sys.exit(1)

        print_info(f"Testing email delivery to: {recipient}")

        service = EmailService()

        if not service.is_configured():
            print_error("Email service not configured. Run: python cli.py email setup")
            sys.exit(1)

        print_info("Sending test email...")

        if service.send_test_email(recipient):
            print_success(f"Test email sent successfully to {recipient}")
            print_info("Check your inbox!")
        else:
            print_error("Failed to send test email")
            sys.exit(1)

    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)
        sys.exit(1)


@email_group.command(name="status")
def email_status():
    """Show email configuration status"""

    print_header("Email Configuration Status")

    import os

    config = {
        "Enabled": os.getenv("EMAIL_ENABLED", "false"),
        "Recipient": os.getenv("EMAIL_RECIPIENT", "(not set)"),
        "Send on Completion": os.getenv("EMAIL_SEND_ON_COMPLETION", "true"),
        "Min Matches": os.getenv("EMAIL_MIN_MATCHES", "1"),
        "Subject Prefix": os.getenv("EMAIL_SUBJECT_PREFIX", "[Job Matcher]"),
    }

    print_key_value_table(config, title="Email Settings")

    # Check credentials
    creds_file = Path("credentials/gmail_client_secrets.json")
    token_file = Path("credentials/gmail_token.json")

    print_section("OAuth2 Status")

    if creds_file.exists():
        print_success(f"Client secrets found: {creds_file}")
    else:
        print_error(f"Client secrets missing: {creds_file}")
        print_info("Run: python cli.py email setup")

    if token_file.exists():
        print_success(f"Access token found: {token_file}")
    else:
        print_info(f"Access token not found: {token_file}")
        print_info("Token will be created on first use")


def find_latest_report():
    """Find most recent report file by timestamp

    Returns:
        Path to latest report file, or None if no reports found
    """
    reports_dir = ProfilePaths().reports_dir

    if not reports_dir.exists():
        return None

    # Find all job_report_*.html files
    report_files = list(reports_dir.glob("job_report_*.html"))

    if not report_files:
        return None

    # Sort by modification time (most recent first)
    report_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    return report_files[0]


def find_latest_reports_by_source():
    """Find most recent report for each source

    Returns:
        Dict mapping source name to report path
    """
    reports_dir = ProfilePaths().reports_dir
    if not reports_dir.exists():
        return {}

    sources = {}
    for source in ["indeed", "glassdoor", "linkedin", "ziprecruiter"]:
        pattern = f"job_report_{source}_*.html"
        report_files = list(reports_dir.glob(pattern))

        if report_files:
            report_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            sources[source] = report_files[0]

    return sources


def extract_source_data_from_html(html_path: str) -> str:
    """Extract source data file path from HTML metadata

    Args:
        html_path: Path to HTML report file

    Returns:
        Path to source JSON file, or None if not found
    """
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            # Read first 1000 characters (metadata is in <head>)
            content = f.read(1000)

            # Look for <meta name="source-data" content="...">
            import re
            match = re.search(r'<meta name="source-data" content="([^"]+)"', content)

            if match:
                return match.group(1)
    except Exception:
        pass

    return None


@email_group.command(name="send")
@click.argument("report_file", required=False)
@click.option("--recipient", help="Email recipient (default: from .env)")
@click.option("--subject", help="Email subject (default: auto-generated)")
def send_email(report_file, recipient, subject):
    """Send email with job report(s)

    If no report file is specified, automatically detects and sends ALL available
    source reports (Indeed, Glassdoor, etc.) in a single multi-source email.

    If a specific report file is provided, sends only that single report.

    Examples:
        python cli.py email send  # Sends all sources (multi-source email)
        python cli.py email send reports/job_report_indeed_20251011.html  # Single report
        python cli.py email send --recipient you@example.com
    """

    print_header("Send Email Report")

    try:
        import os
        import json
        from job_matcher.email_service import EmailService

        service = EmailService()

        if not service.is_configured():
            print_error("Email service not configured. Run: python cli.py email setup")
            sys.exit(1)

        # Get recipients: use --recipient flag if provided, otherwise use profile config
        if recipient:
            # Explicit override via --recipient flag
            recipients = [recipient]
        else:
            # Use profile's configured recipients
            recipients = service.get_recipients()
            if not recipients:
                print_error("No recipients configured. Use --recipient flag or configure profile email settings")
                print_info("Run: cli profile email set <profile> --recipients email@example.com")
                sys.exit(1)

        subject_prefix = service.get_subject_prefix()

        # MULTI-SOURCE PATH: No report file specified
        if not report_file:
            print_info("No report specified, finding all available source reports...")

            available_sources = find_latest_reports_by_source()

            if not available_sources:
                print_error("No reports found in reports/ directory")
                print_info("Run 'python cli.py match' to generate reports first")
                sys.exit(1)

            print_success(f"Found reports for: {', '.join(available_sources.keys())}")

            # Load jobs for each source
            jobs_by_source = []
            report_paths = []

            for source, report_path in available_sources.items():
                print_info(f"Loading {source} jobs...")

                # Find the LATEST matched JSON for this source in profile's data dir
                paths = ProfilePaths()

                # Pattern: jobs_{source}_matched_*.json
                pattern = f"jobs_{source}_matched_*.json"
                matched_files = list(paths.data_dir.glob(pattern))

                if matched_files:
                    # Sort by modification time, get most recent
                    matched_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    jobs_file = matched_files[0]

                    with open(jobs_file, "r", encoding="utf-8") as f:
                        jobs = json.load(f)
                    print_success(f"  [SUCCESS] Loaded {len(jobs)} {source} jobs from {jobs_file.name}")
                    jobs_by_source.append((source, jobs))
                    report_paths.append(str(report_path))
                else:
                    print_info(f"  [WARNING] No matched jobs found for {source}, skipping")

            if not jobs_by_source:
                print_error("No jobs data found for any source")
                sys.exit(1)

            print_info(f"\nSending multi-source report to: {', '.join(recipients)}")
            print_info(f"  Sources: {', '.join([s for s, _ in jobs_by_source])}")
            print_info(f"  Total jobs: {sum(len(jobs) for _, jobs in jobs_by_source)}")
            print_info(f"  Reports attached: {len(report_paths)}")

            # Send multi-source email to all recipients
            success_count = 0
            for rec in recipients:
                if service.send_multi_source_report(
                    recipient=rec,
                    jobs_by_source=jobs_by_source,
                    report_paths=report_paths,
                    subject_prefix=subject_prefix,
                ):
                    success_count += 1

            if success_count > 0:
                print_success(f"\nEmail sent successfully to {success_count} recipient(s)")
            else:
                print_error("Failed to send email to any recipients")
                sys.exit(1)

        # SINGLE-SOURCE PATH: Specific report file provided
        else:
            # Validate report file exists
            if not Path(report_file).exists():
                print_error(f"Report file not found: {report_file}")
                sys.exit(1)

            print_info(f"Sending single report to: {', '.join(recipients)}")
            print_info(f"Report file: {report_file}")

            # Extract source from report filename
            # Pattern: job_report_{source}_*.html
            report_name = Path(report_file).name
            import re
            source_match = re.search(r'job_report_(\w+)_', report_name)

            if source_match:
                source = source_match.group(1)

                # Find the LATEST matched JSON for this source in profile's data dir
                paths = ProfilePaths()
                pattern = f"jobs_{source}_matched_*.json"
                matched_files = list(paths.data_dir.glob(pattern))

                if matched_files:
                    # Sort by modification time, get most recent
                    matched_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    jobs_file = matched_files[0]

                    print_success(f"Loading latest jobs data from: {jobs_file.name}")
                    with open(jobs_file, "r", encoding="utf-8") as f:
                        jobs = json.load(f)
                else:
                    print_info(f"No matched jobs found for {source}, sending minimal email")
                    jobs = []
            else:
                print_info("Could not determine source from report filename, sending minimal email")
                jobs = []

            # Send to all recipients
            success_count = 0
            for rec in recipients:
                if service.send_report(
                    recipient=rec,
                    jobs=jobs,
                    report_path=report_file,
                    subject_prefix=subject_prefix,
                ):
                    success_count += 1

            if success_count > 0:
                print_success(f"Email sent successfully to {success_count} recipient(s)")
            else:
                print_error("Failed to send email to any recipients")
                sys.exit(1)

    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)
        sys.exit(1)
