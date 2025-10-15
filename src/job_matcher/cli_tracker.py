"""
Job Tracker CLI Commands

Commands for managing job tracking database.
"""

import sys
from pathlib import Path

import click

# Add parent directory to path for cli_utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli.utils import (
    print_header,
    print_section,
    print_success,
    print_error,
    print_info,
    print_table,
    print_key_value_table,
    confirm,
    handle_error,
    cli_state,
)


@click.group(name="tracker")
def tracker_group():
    """Job tracker management commands"""
    pass


@tracker_group.command(name="stats")
def show_stats():
    """Show job tracker statistics"""

    print_header("Job Tracker Statistics")

    try:
        from job_matcher.job_tracker import JobTracker

        tracker = JobTracker()
        stats = tracker.get_stats()

        # Overall stats
        print_section("Overall Statistics")
        overall = {
            "Total Jobs Tracked": stats['total_jobs'],
            "Average Match Score": f"{stats['avg_score']:.1f}",
            "High Matches (≥80)": stats['high_matches'],
            "Medium Matches (70-79)": stats['medium_matches'],
            "Low Matches (<70)": stats['low_matches'],
            "Reposted Jobs": stats['reposted_jobs'],
        }
        print_key_value_table(overall, title="Statistics")

    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)
        sys.exit(1)


@tracker_group.command(name="list")
@click.option("--limit", type=int, default=20, help="Number of jobs to show")
@click.option("--min-score", type=int, help="Filter by minimum score")
@click.option("--sort-by", type=click.Choice(["score", "date"]), default="date", help="Sort by")
def list_jobs(limit, min_score, sort_by):
    """List tracked jobs"""

    print_header("Tracked Jobs")

    try:
        from job_matcher.job_tracker import JobTracker

        tracker = JobTracker()

        # Get jobs from database
        import sqlite3
        import os

        db_path = os.getenv("JOB_TRACKER_DB", "job_tracker.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        query = "SELECT job_title, company, location, match_score, processed_at FROM jobs"

        if min_score:
            query += f" WHERE match_score >= {min_score}"

        if sort_by == "score":
            query += " ORDER BY match_score DESC"
        else:
            query += " ORDER BY processed_at DESC"

        query += f" LIMIT {limit}"

        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            print_info("No jobs found")
            return

        # Format for display
        display_rows = []
        for row in rows:
            title, company, location, score, date = row
            display_rows.append([
                title[:40],
                company[:25],
                location[:25],
                f"{score}",
                date[:10],
            ])

        print_table(
            title=f"Tracked Jobs (showing {len(rows)} of {len(rows)})",
            columns=["Job Title", "Company", "Location", "Score", "Date"],
            rows=display_rows,
            show_lines=False,
        )

    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)
        sys.exit(1)


@tracker_group.command(name="reset")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def reset_tracker(yes):
    """Reset job tracker database"""

    print_header("Reset Job Tracker")

    if not yes:
        print_info("This will delete all tracked jobs from the database")
        if not confirm("Are you sure you want to reset the tracker?"):
            print_info("Reset cancelled")
            return

    try:
        from job_matcher.job_tracker import JobTracker
        import os

        db_path = os.getenv("JOB_TRACKER_DB", "job_tracker.db")

        if Path(db_path).exists():
            Path(db_path).unlink()
            print_success(f"Deleted: {db_path}")

        # Recreate database
        tracker = JobTracker()
        print_success("Job tracker reset successfully")

    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)
        sys.exit(1)


@tracker_group.command(name="export")
@click.option("--output", "-o", default="tracker_export.json", help="Output file")
@click.option("--format", "output_format", type=click.Choice(["json", "csv"]), default="json", help="Output format")
def export_tracker(output, output_format):
    """Export tracker database to JSON or CSV"""

    print_header("Export Job Tracker")

    try:
        import sqlite3
        import json
        import csv
        import os

        db_path = os.getenv("JOB_TRACKER_DB", "job_tracker.db")

        if not Path(db_path).exists():
            print_error(f"Tracker database not found: {db_path}")
            sys.exit(1)

        # Query all jobs
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT job_url, job_title, company, location, match_score, processed_at FROM jobs")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            print_info("No jobs to export")
            return

        # Export based on format
        if output_format == "json":
            jobs = []
            for row in rows:
                jobs.append({
                    "job_url": row[0],
                    "job_title": row[1],
                    "company": row[2],
                    "location": row[3],
                    "match_score": row[4],
                    "processed_at": row[5],
                })

            with open(output, "w") as f:
                json.dump(jobs, f, indent=2)

        else:  # CSV
            with open(output, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["job_url", "job_title", "company", "location", "match_score", "processed_at"])
                writer.writerows(rows)

        print_success(f"Exported {len(rows)} jobs to: {output}")

    except Exception as e:
        handle_error(e, verbose=cli_state.verbose)
        sys.exit(1)
