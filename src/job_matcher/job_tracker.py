"""
JobTracker - SQLite database for tracking processed jobs

Prevents duplicate job processing across multiple reports by tracking
job URLs and their match scores.
"""

import os
import sys
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for profile_manager import
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.profile_manager import ProfilePaths

load_dotenv()


class JobTracker:
    """Track processed jobs to prevent duplicates"""

    def __init__(self, db_path: Optional[str] = None, profile_name: Optional[str] = None):
        """
        Initialize JobTracker

        Args:
            db_path: Path to SQLite database file (default: from profile)
            profile_name: Profile name (default: from .env ACTIVE_PROFILE)
        """
        # Get profile paths
        paths = ProfilePaths(profile_name)

        # Use profile path as default, or custom path if provided
        self.db_path = db_path or os.getenv("JOB_TRACKER_DB", str(paths.job_tracker_db))
        self._init_database()

    def _init_database(self):
        """Create database and tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create jobs table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_url TEXT UNIQUE NOT NULL,
                job_title TEXT,
                company TEXT,
                location TEXT,
                match_score INTEGER,
                report_date TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                times_seen INTEGER DEFAULT 1
            )
        """
        )

        # Create index on job_url for fast lookups
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_job_url
            ON processed_jobs(job_url)
        """
        )

        # Create index on match_score for filtering
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_match_score
            ON processed_jobs(match_score)
        """
        )

        conn.commit()
        conn.close()

    def is_processed(self, job_url: str) -> bool:
        """
        Check if a job has been processed before

        Args:
            job_url: The job posting URL

        Returns:
            True if job has been processed, False otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM processed_jobs WHERE job_url = ?", (job_url,)
        )
        count = cursor.fetchone()[0]

        conn.close()
        return count > 0

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
            # Update existing entry
            return self._update_job(job_url, match_score)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_date = report_date or datetime.now().strftime("%Y-%m-%d")

        try:
            cursor.execute(
                """
                INSERT INTO processed_jobs
                (job_url, job_title, company, location, match_score,
                 report_date, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    job_url,
                    job_title,
                    company,
                    location,
                    match_score,
                    report_date,
                    now,
                    now,
                ),
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            """
            UPDATE processed_jobs
            SET last_seen = ?,
                times_seen = times_seen + 1,
                match_score = ?
            WHERE job_url = ?
        """,
            (now, match_score, job_url),
        )

        conn.commit()
        conn.close()
        return True

    def get_job(self, job_url: str) -> Optional[Dict[str, Any]]:
        """
        Get job information from tracker

        Args:
            job_url: The job posting URL

        Returns:
            Job info dict or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM processed_jobs WHERE job_url = ?", (job_url,))
        row = cursor.fetchone()

        conn.close()

        if row:
            return dict(row)
        return None

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
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM processed_jobs"
        params = []

        if min_score is not None:
            query += " WHERE match_score >= ?"
            params.append(min_score)

        query += " ORDER BY match_score DESC, last_seen DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        conn.close()

        return [dict(row) for row in rows]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about processed jobs

        Returns:
            Stats dict with counts and averages
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total jobs
        cursor.execute("SELECT COUNT(*) FROM processed_jobs")
        total_jobs = cursor.fetchone()[0]

        # Average match score
        cursor.execute("SELECT AVG(match_score) FROM processed_jobs")
        avg_score = cursor.fetchone()[0] or 0

        # High matches (>= 80)
        cursor.execute("SELECT COUNT(*) FROM processed_jobs WHERE match_score >= 80")
        high_matches = cursor.fetchone()[0]

        # Medium matches (70-79)
        cursor.execute(
            "SELECT COUNT(*) FROM processed_jobs WHERE match_score >= 70 AND match_score < 80"
        )
        medium_matches = cursor.fetchone()[0]

        # Low matches (< 70)
        cursor.execute("SELECT COUNT(*) FROM processed_jobs WHERE match_score < 70")
        low_matches = cursor.fetchone()[0]

        # Reposted jobs (seen more than once)
        cursor.execute("SELECT COUNT(*) FROM processed_jobs WHERE times_seen > 1")
        reposted_jobs = cursor.fetchone()[0]

        conn.close()

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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM processed_jobs
            WHERE julianday('now') - julianday(last_seen) > ?
        """,
            (days,),
        )

        removed = cursor.rowcount
        conn.commit()
        conn.close()

        return removed

    def reset(self):
        """Clear all jobs from tracker (use with caution!)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM processed_jobs")
        conn.commit()
        conn.close()


if __name__ == "__main__":
    # Test the tracker
    print("Testing JobTracker...")
    tracker = JobTracker()

    print(f"Database: {tracker.db_path}")

    # Get stats
    stats = tracker.get_stats()
    print("\nCurrent Statistics:")
    print(f"  Total jobs: {stats['total_jobs']}")
    print(f"  Average score: {stats['avg_score']}")
    print(f"  High matches (≥80): {stats['high_matches']}")
    print(f"  Medium matches (70-79): {stats['medium_matches']}")
    print(f"  Low matches (<70): {stats['low_matches']}")
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
