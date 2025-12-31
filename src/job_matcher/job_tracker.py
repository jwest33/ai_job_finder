"""
JobTracker - DuckDB database for tracking processed jobs

Prevents duplicate job processing across multiple reports by tracking
job URLs and their match scores.
"""

import os
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import get_database
from src.utils.profile_manager import ProfilePaths

load_dotenv()


class JobTracker:
    """Track processed jobs to prevent duplicates"""

    def __init__(self, db_path: Optional[str] = None, profile_name: Optional[str] = None):
        """
        Initialize JobTracker

        Args:
            db_path: Ignored (kept for compatibility, uses shared DuckDB)
            profile_name: Profile name (default: from .env ACTIVE_PROFILE)
        """
        self.db = get_database(profile_name)
        self.paths = ProfilePaths(profile_name)

    def is_processed(self, job_url: str) -> bool:
        """
        Check if a job has been processed before

        Args:
            job_url: The job posting URL

        Returns:
            True if job has been processed, False otherwise
        """
        result = self.db.fetchone(
            "SELECT COUNT(*) FROM processed_jobs WHERE job_url = ?",
            (job_url,)
        )
        return result[0] > 0 if result else False

    def add_job(
        self,
        job_url: str,
        job_title: str,
        company: str,
        location: str,
        match_score: int,
        report_date: Optional[str] = None,
    ) -> bool:
        """
        Add a processed job to the tracker

        Args:
            job_url: The job posting URL
            job_title: Job title
            company: Company name
            location: Job location
            match_score: Match score (0-100)
            report_date: Date of report (default: today)

        Returns:
            True if job was added, False if it already exists
        """
        if self.is_processed(job_url):
            return self._update_job(job_url, match_score)

        now = datetime.now()
        report_date = report_date or now.strftime("%Y-%m-%d")

        try:
            self.db.execute("""
                INSERT INTO processed_jobs
                (job_url, job_title, company, location, match_score,
                 report_date, first_seen, last_seen, times_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_url,
                job_title,
                company,
                location,
                match_score,
                report_date,
                now,
                now,
                1,
            ))
            return True
        except Exception:
            return False

    def _update_job(self, job_url: str, match_score: int) -> bool:
        """
        Update an existing job entry (called when job is seen again)

        Args:
            job_url: The job posting URL
            match_score: New match score

        Returns:
            True if updated successfully
        """
        now = datetime.now()

        self.db.execute("""
            UPDATE processed_jobs
            SET last_seen = ?,
                times_seen = times_seen + 1,
                match_score = ?
            WHERE job_url = ?
        """, (now, match_score, job_url))

        return True

    def get_job(self, job_url: str) -> Optional[Dict[str, Any]]:
        """
        Get job information from tracker

        Args:
            job_url: The job posting URL

        Returns:
            Job info dict or None if not found
        """
        df = self.db.fetchdf(
            "SELECT * FROM processed_jobs WHERE job_url = ?",
            (job_url,)
        )

        if df.empty:
            return None

        return df.iloc[0].to_dict()

    def get_all_jobs(
        self, min_score: Optional[int] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all processed jobs

        Args:
            min_score: Filter by minimum match score
            limit: Limit number of results

        Returns:
            List of job info dicts
        """
        query = "SELECT * FROM processed_jobs"
        params = []

        if min_score is not None:
            query += " WHERE match_score >= ?"
            params.append(min_score)

        query += " ORDER BY match_score DESC, last_seen DESC"

        if limit:
            query += f" LIMIT {limit}"

        df = self.db.fetchdf(query, tuple(params) if params else None)

        if df.empty:
            return []

        return df.to_dict("records")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about processed jobs

        Returns:
            Stats dict with counts and averages
        """
        # Total jobs
        result = self.db.fetchone("SELECT COUNT(*) FROM processed_jobs")
        total_jobs = result[0] if result else 0

        # Average match score
        result = self.db.fetchone("SELECT AVG(match_score) FROM processed_jobs")
        avg_score = result[0] if result and result[0] else 0

        # High matches (>= 80)
        result = self.db.fetchone(
            "SELECT COUNT(*) FROM processed_jobs WHERE match_score >= 80"
        )
        high_matches = result[0] if result else 0

        # Medium matches (60-79)
        result = self.db.fetchone(
            "SELECT COUNT(*) FROM processed_jobs WHERE match_score >= 60 AND match_score < 80"
        )
        medium_matches = result[0] if result else 0

        # Low matches (< 60)
        result = self.db.fetchone(
            "SELECT COUNT(*) FROM processed_jobs WHERE match_score < 60"
        )
        low_matches = result[0] if result else 0

        # Reposted jobs (seen more than once)
        result = self.db.fetchone(
            "SELECT COUNT(*) FROM processed_jobs WHERE times_seen > 1"
        )
        reposted_jobs = result[0] if result else 0

        return {
            "total_jobs": total_jobs,
            "avg_score": round(avg_score, 1),
            "high_matches": high_matches,
            "medium_matches": medium_matches,
            "low_matches": low_matches,
            "reposted_jobs": reposted_jobs,
        }

    def clear_old_jobs(self, days: int = 30) -> int:
        """
        Remove jobs older than specified days

        Args:
            days: Number of days to keep

        Returns:
            Number of jobs removed
        """
        # Get count before delete
        result = self.db.fetchone(
            "SELECT COUNT(*) FROM processed_jobs WHERE last_seen < CURRENT_TIMESTAMP - INTERVAL ? DAY",
            (days,)
        )
        count = result[0] if result else 0

        self.db.execute(
            "DELETE FROM processed_jobs WHERE last_seen < CURRENT_TIMESTAMP - INTERVAL ? DAY",
            (days,)
        )

        return count

    def get_jobs_by_date_range(
        self,
        from_date: str,
        to_date: str,
        sources: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get jobs processed within a date range, optionally filtered by source

        Args:
            from_date: Start date (YYYY-MM-DD format)
            to_date: End date (YYYY-MM-DD format)
            sources: List of source names (e.g., ['indeed', 'linkedin']) to filter by

        Returns:
            List of job info dicts matching criteria
        """
        query = """
            SELECT * FROM processed_jobs
            WHERE report_date >= ? AND report_date <= ?
        """
        params = [from_date, to_date]

        # Filter by source if specified (check URL patterns) - parameterized to prevent SQL injection
        if sources:
            source_placeholders = []
            for source in sources:
                source_placeholders.append("job_url LIKE ?")
                params.append(f'%{source.lower()}%')
            if source_placeholders:
                query += f" AND ({' OR '.join(source_placeholders)})"

        query += " ORDER BY report_date DESC, match_score DESC"

        df = self.db.fetchdf(query, tuple(params))

        if df.empty:
            return []

        return df.to_dict("records")

    def delete_jobs_by_date_range(
        self,
        from_date: str,
        to_date: str,
        sources: Optional[List[str]] = None,
    ) -> int:
        """
        Delete jobs processed within a date range, optionally filtered by source

        Args:
            from_date: Start date (YYYY-MM-DD format)
            to_date: End date (YYYY-MM-DD format)
            sources: List of source names (e.g., ['indeed', 'linkedin']) to filter by

        Returns:
            Number of jobs deleted
        """
        # Get count first
        count_query = """
            SELECT COUNT(*) FROM processed_jobs
            WHERE report_date >= ? AND report_date <= ?
        """
        params = [from_date, to_date]

        # Parameterized source filtering to prevent SQL injection
        if sources:
            source_placeholders = []
            for source in sources:
                source_placeholders.append("job_url LIKE ?")
                params.append(f'%{source.lower()}%')
            if source_placeholders:
                count_query += f" AND ({' OR '.join(source_placeholders)})"

        result = self.db.fetchone(count_query, tuple(params))
        count = result[0] if result else 0

        # Now delete - rebuild params for delete query
        delete_params = [from_date, to_date]
        delete_query = """
            DELETE FROM processed_jobs
            WHERE report_date >= ? AND report_date <= ?
        """

        if sources:
            source_placeholders = []
            for source in sources:
                source_placeholders.append("job_url LIKE ?")
                delete_params.append(f'%{source.lower()}%')
            if source_placeholders:
                delete_query += f" AND ({' OR '.join(source_placeholders)})"

        self.db.execute(delete_query, tuple(delete_params))

        return count

    def reset(self):
        """Clear all jobs from tracker (use with caution!)"""
        self.db.execute("DELETE FROM processed_jobs")


if __name__ == "__main__":
    # Test the tracker
    print("Testing JobTracker...")
    tracker = JobTracker()

    print(f"Database: {tracker.db.db_path}")

    # Get stats
    stats = tracker.get_stats()
    print("\nCurrent Statistics:")
    print(f"  Total jobs: {stats['total_jobs']}")
    print(f"  Average score: {stats['avg_score']}")
    print(f"  High matches (>=80): {stats['high_matches']}")
    print(f"  Medium matches (60-79): {stats['medium_matches']}")
    print(f"  Low matches (<60): {stats['low_matches']}")
    print(f"  Reposted jobs: {stats['reposted_jobs']}")

    # Test adding a job
    test_url = "https://example.com/job/test123"
    if not tracker.is_processed(test_url):
        print(f"\nAdding test job: {test_url}")
        tracker.add_job(
            job_url=test_url,
            job_title="Test Job",
            company="Test Company",
            location="Remote",
            match_score=85,
        )
        print("Test job added")
    else:
        print(f"\n[WARNING] Test job already exists: {test_url}")

    print("\nJobTracker test complete")
