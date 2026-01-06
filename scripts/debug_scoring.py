#!/usr/bin/env python
"""
Debug script to compare scoring between direct score_job() and batch queue methods.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.job_matcher.llama_client import LlamaClient
from src.job_matcher.resume_analyzer import ResumeAnalyzer
from src.job_matcher.match_scorer import MatchScorer
from src.core.storage import JobStorage


def get_job():
    """Load the DraftKings job from DB."""
    storage = JobStorage()
    job = storage.get_job('https://www.indeed.com/viewjob?jk=65e4b37b7211d13d')

    # Sanitize like tune_matcher does
    import numpy as np
    import pandas as pd

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


def main():
    print("=" * 60)
    print("SCORING METHOD COMPARISON")
    print("=" * 60)

    # Initialize
    client = LlamaClient()
    analyzer = ResumeAnalyzer()
    analyzer.load_all()
    scorer = MatchScorer(client, analyzer)

    # Get job
    job = get_job()
    print(f"\nJob: {job['title']} @ {job['company']}")

    # Method 1: Direct score_job() - same as tune_matcher
    print("\n" + "-" * 60)
    print("METHOD 1: Direct score_job() [tune_matcher style]")
    print("-" * 60)

    result1 = scorer.score_job(job.copy(), use_hybrid_scoring=True)
    if result1:
        breakdown1 = result1.get('scoring_breakdown', {})
        print(f"  Deterministic: {breakdown1.get('deterministic_score', 'N/A')}/40")
        print(f"  AI Score: {breakdown1.get('ai_score', 'N/A')}/100")
        print(f"  Combined: {result1.get('match_score', 'N/A')}/100")
        print(f"  Reasoning: {result1.get('reasoning', '')[:150]}...")
    else:
        print("  FAILED")

    # Method 2: Batch queue method - same as API
    print("\n" + "-" * 60)
    print("METHOD 2: score_jobs_batch_queued() [API style]")
    print("-" * 60)

    def progress(current, total, j):
        pass

    # Use a fresh copy of the job
    jobs = [job.copy()]
    results2 = scorer.score_jobs_batch_queued(jobs, progress, apply_pre_filters=False)

    if results2:
        result2 = results2[0]
        breakdown2 = result2.get('scoring_breakdown', {})
        print(f"  Deterministic: {breakdown2.get('deterministic_score', 'N/A')}/40")
        print(f"  AI Score: {breakdown2.get('ai_score', 'N/A')}/100")
        print(f"  Combined: {result2.get('match_score', 'N/A')}/100")
        print(f"  Reasoning: {result2.get('reasoning', '')[:150]}...")
    else:
        print("  FAILED - no results")

    # Compare
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)
    if result1 and results2:
        score1 = result1.get('match_score', 0)
        score2 = results2[0].get('match_score', 0)
        ai1 = result1.get('scoring_breakdown', {}).get('ai_score', 0)
        ai2 = results2[0].get('scoring_breakdown', {}).get('ai_score', 0)

        print(f"  Direct score_job():        {score1}/100 (AI: {ai1})")
        print(f"  Batch queue:               {score2}/100 (AI: {ai2})")
        print(f"  Difference:                {abs(score1 - score2)} points")

        if abs(score1 - score2) > 5:
            print("\n  *** SIGNIFICANT DISCREPANCY DETECTED ***")

    print("\nDone!")


if __name__ == "__main__":
    main()
