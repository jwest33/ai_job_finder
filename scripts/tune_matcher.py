#!/usr/bin/env python
"""
Ad-hoc interface for tuning job matching against a single job.

Usage:
    python scripts/tune_matcher.py                     # Browse and select from database
    python scripts/tune_matcher.py --search "netflix"  # Search jobs by keyword
    python scripts/tune_matcher.py --url <job_url>     # Fetch job from database by URL
    python scripts/tune_matcher.py --latest            # Use the most recent job from DB
"""

import sys
import json
import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.job_matcher.llama_client import LlamaClient
from src.job_matcher.resume_analyzer import ResumeAnalyzer
from src.job_matcher.match_scorer import MatchScorer
from src.core.storage import JobStorage


def sanitize_job_dict(job: dict) -> dict:
    """
    Convert numpy arrays and pandas types to native Python types.
    This is needed because DataFrame.to_dict() returns numpy arrays for list columns.
    """
    sanitized = {}
    for key, value in job.items():
        if isinstance(value, np.ndarray):
            sanitized[key] = value.tolist()
        elif isinstance(value, (np.integer, np.floating)):
            sanitized[key] = value.item()
        elif isinstance(value, pd.Timestamp):
            sanitized[key] = value.isoformat()
        elif pd.isna(value):
            sanitized[key] = None
        else:
            sanitized[key] = value
    return sanitized


def get_job_from_db(job_url: str = None, latest: bool = False) -> dict:
    """Fetch a job from the database."""
    storage = JobStorage()

    if latest:
        df = storage.load_all_jobs()
        if df is not None and not df.empty:
            df = df.sort_values('date_posted', ascending=False, na_position='last')
            return sanitize_job_dict(df.iloc[0].to_dict())
        raise ValueError("No jobs found in database")

    if job_url:
        job = storage.get_job(job_url)
        if job:
            return sanitize_job_dict(job)
        raise ValueError(f"Job not found: {job_url}")

    return None


def browse_jobs(search: str = None) -> dict:
    """Browse jobs from database and let user select one."""
    storage = JobStorage()

    # Get jobs from database as DataFrame
    df = storage.load_all_jobs()

    if df is None or df.empty:
        print("No jobs found in database")
        return None

    # Filter by search term if provided
    if search:
        search_lower = search.lower()
        mask = (
            df['title'].str.lower().str.contains(search_lower, na=False) |
            df['company'].str.lower().str.contains(search_lower, na=False) |
            df['description'].str.lower().str.contains(search_lower, na=False)
        )
        df = df[mask]

    if df.empty:
        print(f"No jobs found matching '{search}'")
        return None

    # Sort by date_posted desc, limit to 50
    df = df.sort_values('date_posted', ascending=False, na_position='last').head(50)

    # Convert to list of dicts
    jobs = df.to_dict('records')

    # Display jobs
    print("\n" + "=" * 80)
    print(f"JOBS IN DATABASE ({len(jobs)} shown)")
    print("=" * 80)

    for i, job in enumerate(jobs):
        title = str(job.get('title', 'Unknown'))[:40]
        company = str(job.get('company', 'Unknown'))[:20]

        # Handle score (could be None, NaN, or valid number)
        score = job.get('match_score')
        if score is not None and not (isinstance(score, float) and math.isnan(score)):
            score_str = f"{int(score):3d}"
        else:
            score_str = "  -"

        remote = "Remote" if job.get('remote') else "Onsite"

        # Handle salary (could be None, NaN, or valid number)
        salary_max = job.get('salary_max')
        if salary_max is not None and not (isinstance(salary_max, float) and math.isnan(salary_max)):
            salary_str = f"${float(salary_max)/1000:.0f}k"
        else:
            salary_str = "    -"

        print(f"  [{i+1:2d}] {score_str} | {salary_str:>6} | {remote:6} | {title:<40} @ {company}")

    print("\n" + "-" * 80)
    print("Enter number to select, 's' to search, or 'q' to quit")

    while True:
        try:
            choice = input("\nSelect job: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None

        if choice == 'q':
            return None
        elif choice == 's':
            search_term = input("Search term: ").strip()
            return browse_jobs(search=search_term)
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(jobs):
                    return sanitize_job_dict(jobs[idx])
                else:
                    print(f"Invalid selection. Enter 1-{len(jobs)}")
            except ValueError:
                print("Enter a number, 's' to search, or 'q' to quit")


def display_job_summary(job: dict):
    """Display a summary of the job."""
    print("\n" + "=" * 60)
    print("JOB SUMMARY")
    print("=" * 60)
    print(f"Title:    {job.get('title', 'Unknown')}")
    print(f"Company:  {job.get('company', 'Unknown')}")
    print(f"Location: {job.get('location', 'Unknown')}")
    print(f"Remote:   {job.get('remote', False)}")

    salary_min = job.get('salary_min')
    salary_max = job.get('salary_max')
    if salary_min or salary_max:
        print(f"Salary:   ${salary_min:,.0f} - ${salary_max:,.0f}" if salary_min and salary_max else f"Salary: ${salary_min or salary_max:,.0f}")

    print(f"URL:      {job.get('job_url', 'N/A')[:60]}...")
    print()


def display_scoring_result(result: dict, job: dict):
    """Display the scoring result in detail."""
    print("\n" + "=" * 60)
    print("SCORING RESULT")
    print("=" * 60)

    score = result.get('match_score', 0)

    # Color-coded score
    if score >= 85:
        score_label = "STRONG MATCH"
    elif score >= 70:
        score_label = "GOOD MATCH"
    elif score >= 50:
        score_label = "MODERATE"
    else:
        score_label = "POOR MATCH"

    print(f"\nSCORE: {score}/100 ({score_label})")
    print("-" * 40)

    # Scoring breakdown if available
    breakdown = result.get('scoring_breakdown')
    if breakdown:
        print("\nDETERMINISTIC BREAKDOWN:")
        det_breakdown = breakdown.get('deterministic_breakdown', {})
        print(f"  Title:    {det_breakdown.get('title', 'N/A')}/20")
        print(f"  Salary:   {det_breakdown.get('salary', 'N/A')}/10")
        print(f"  Location: {det_breakdown.get('location', 'N/A')}/10")
        print(f"  Total:    {breakdown.get('deterministic_score', 'N/A')}/40")
        print(f"\nAI SCORE: {breakdown.get('ai_score', 'N/A')}/100")
        print(f"COMBINED: {breakdown.get('combined_score', 'N/A')}/100")

    print("\n" + "-" * 40)
    print("REASONING:")
    print("-" * 40)
    print(result.get('reasoning', 'No reasoning provided'))

    # Preference checks
    pref_checks = result.get('preference_checks', {})
    if pref_checks:
        print("\n" + "-" * 40)
        print("PREFERENCE CHECKS:")
        print("-" * 40)
        for pref, passed in pref_checks.items():
            status = "PASS" if passed else "FAIL"
            print(f"  {pref}: {status}")

    # Matched requirements
    matched_reqs = result.get('matched_requirements', {})
    if matched_reqs:
        print("\n" + "-" * 40)
        print("MATCHED REQUIREMENTS:")
        print("-" * 40)
        for req, value in matched_reqs.items():
            print(f"  {req}: {value}")


def show_prompt(scorer: MatchScorer, job: dict):
    """Show the full prompt that would be sent to the LLM."""
    print("\n" + "=" * 60)
    print("FULL PROMPT (for debugging)")
    print("=" * 60)
    prompt = scorer._create_scoring_prompt(job)
    print(prompt)
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Tune job matching against a single job")
    parser.add_argument("--url", help="Job URL to fetch from database")
    parser.add_argument("--search", help="Search jobs by keyword")
    parser.add_argument("--latest", action="store_true", help="Use the most recent job from database")
    parser.add_argument("--show-prompt", action="store_true", help="Show the full prompt sent to LLM")
    parser.add_argument("--no-hybrid", action="store_true", help="Disable hybrid scoring (AI only)")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("JOB MATCHER TUNING INTERFACE")
    print("=" * 60)

    # Initialize components
    print("\nInitializing...")
    client = LlamaClient()
    analyzer = ResumeAnalyzer()

    try:
        analyzer.load_all()
        print("Loaded resume and requirements")
    except Exception as e:
        print(f"Error loading resume/requirements: {e}")
        return 1

    scorer = MatchScorer(client, analyzer)

    # Get the job
    job = None

    if args.url:
        job = get_job_from_db(job_url=args.url)
        print(f"Loaded job from database: {args.url}")
    elif args.latest:
        job = get_job_from_db(latest=True)
        print("Loaded latest job from database")
    else:
        # Default: browse jobs from database
        job = browse_jobs(search=args.search)

    if not job:
        print("No job selected")
        return 1

    # Display job summary
    display_job_summary(job)

    # Show prompt if requested
    if args.show_prompt:
        show_prompt(scorer, job)

        print("\nContinue with scoring? (y/n): ", end="")
        if input().lower() != 'y':
            return 0

    # Score the job
    print("\nScoring job...")
    use_hybrid = not args.no_hybrid
    result = scorer.score_job(job, use_hybrid_scoring=use_hybrid)

    if result:
        display_scoring_result(result, job)
    else:
        print("\nScoring FAILED - no result returned")
        return 1

    # Interactive loop for re-scoring
    print("\n" + "=" * 60)
    print("OPTIONS:")
    print("  [p] Show full prompt")
    print("  [r] Re-score this job")
    print("  [b] Browse and select another job")
    print("  [q] Quit")
    print("=" * 60)

    while True:
        try:
            choice = input("\nChoice: ").lower().strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == 'q':
            break
        elif choice == 'p':
            show_prompt(scorer, job)
        elif choice == 'r':
            print("\nRe-scoring job...")
            result = scorer.score_job(job, use_hybrid_scoring=use_hybrid)
            if result:
                display_scoring_result(result, job)
            else:
                print("Scoring FAILED")
        elif choice == 'b':
            new_job = browse_jobs()
            if new_job:
                job = new_job
                display_job_summary(job)
                print("\nScoring job...")
                result = scorer.score_job(job, use_hybrid_scoring=use_hybrid)
                if result:
                    display_scoring_result(result, job)
                else:
                    print("Scoring FAILED")
        else:
            print("Unknown option")

    print("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
