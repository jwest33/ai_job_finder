"""
FailureTracker - Track Failed Job Processing

Tracks jobs that fail during any of the three processing passes
(scoring, analysis, optimization) with detailed error information
for later retry and analysis.

Thread-safe for multi-threaded processing.
"""

import os
import sys
import json
import sqlite3
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for profile_manager import
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.profile_manager import ProfilePaths

load_dotenv()


# Error type constants
class ErrorType:
    """Standard error type classifications"""
    JSON_PARSE_ERROR = "JSON_PARSE_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class FailureTracker:
    """Track failed job processing attempts for retry and analysis"""

    def __init__(self, db_path: Optional[str] = None, profile_name: Optional[str] = None):
        """
        Initialize FailureTracker

        Args:
            db_path: Path to SQLite database file (default: from profile)
            profile_name: Profile name (default: from .env ACTIVE_PROFILE)
        """
        # Get profile paths
        paths = ProfilePaths(profile_name)

        # Use profile path as default, or custom path if provided
        self.db_path = db_path or os.getenv("FAILURE_TRACKER_DB", str(paths.failure_tracker_db))
        self._lock = threading.Lock()  # Thread-safe operations
        self._init_database()

    def _init_database(self):
        """Create database and tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create failed_jobs table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS failed_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_url TEXT NOT NULL,
                job_title TEXT,
                company TEXT,
                stage TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT,
                failure_count INTEGER DEFAULT 1,
                first_failed TEXT NOT NULL,
                last_failed TEXT NOT NULL,
                raw_job_data TEXT,
                UNIQUE(job_url, stage)
            )
        """
        )

        # Create indexes for fast lookups
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_stage
            ON failed_jobs(stage)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_error_type
            ON failed_jobs(error_type)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_failure_count
            ON failed_jobs(failure_count)
        """
        )

        conn.commit()
        conn.close()

    def record_failure(
        self,
        job: Dict[str, Any],
        stage: str,
        error_type: str,
        error_message: str = ""
    ) -> bool:
        """
        Record a job processing failure (thread-safe)

        Args:
            job: Job dict with at least job_url
            stage: Pipeline stage (scoring, analysis, optimization)
            error_type: Error type constant (from ErrorType class)
            error_message: Detailed error message

        Returns:
            True if recorded successfully
        """
        with self._lock:
            job_url = job.get("job_url", "")
            job_title = job.get("title", "Unknown")
            company = job.get("company", "Unknown")

            if not job_url:
                print("[WARNING] Cannot record failure: missing job_url")
                return False

            # Serialize job data as JSON
            raw_job_data = json.dumps(job, ensure_ascii=False)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if this job/stage combo already exists
            cursor.execute(
                "SELECT id, failure_count FROM failed_jobs WHERE job_url = ? AND stage = ?",
                (job_url, stage)
            )
            existing = cursor.fetchone()

            try:
                if existing:
                    # Update existing failure
                    existing_id, existing_count = existing
                    cursor.execute(
                        """
                        UPDATE failed_jobs
                        SET error_type = ?,
                            error_message = ?,
                            failure_count = ?,
                            last_failed = ?,
                            raw_job_data = ?
                        WHERE id = ?
                    """,
                        (
                            error_type,
                            error_message,
                            existing_count + 1,
                            now,
                            raw_job_data,
                            existing_id
                        )
                    )
                else:
                    # Insert new failure
                    cursor.execute(
                        """
                        INSERT INTO failed_jobs
                        (job_url, job_title, company, stage, error_type,
                         error_message, failure_count, first_failed, last_failed, raw_job_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            job_url,
                            job_title,
                            company,
                            stage,
                            error_type,
                            error_message,
                            1,
                            now,
                            now,
                            raw_job_data
                        )
                    )

                conn.commit()
                conn.close()
                return True

            except sqlite3.Error as e:
                print(f"[WARNING] Database error recording failure: {e}")
                conn.close()
                return False

    def mark_resolved(self, job_url: str, stage: str) -> bool:
        """
        Mark a failed job as resolved (remove from failures)

        Args:
            job_url: Job URL
            stage: Pipeline stage

        Returns:
            True if marked successfully
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM failed_jobs WHERE job_url = ? AND stage = ?",
                (job_url, stage)
            )

            affected = cursor.rowcount
            conn.commit()
            conn.close()

            return affected > 0

    def get_failed_jobs(
        self,
        stage: Optional[str] = None,
        min_failures: int = 1,
        error_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get failed jobs matching criteria

        Args:
            stage: Filter by stage (scoring, analysis, optimization)
            min_failures: Minimum failure count
            error_type: Filter by error type

        Returns:
            List of failed job records with parsed raw_job_data
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM failed_jobs WHERE failure_count >= ?"
        params = [min_failures]

        if stage:
            query += " AND stage = ?"
            params.append(stage)

        if error_type:
            query += " AND error_type = ?"
            params.append(error_type)

        query += " ORDER BY failure_count DESC, last_failed DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        # Parse raw_job_data JSON
        results = []
        for row in rows:
            record = dict(row)
            try:
                record["job_data"] = json.loads(record["raw_job_data"])
            except (json.JSONDecodeError, TypeError):
                record["job_data"] = {}
            results.append(record)

        return results

    def export_failed_jobs(
        self,
        stage: str,
        output_file: str,
        include_metadata: bool = True
    ) -> int:
        """
        Export failed jobs to JSON file for retry

        Args:
            stage: Pipeline stage to export
            output_file: Output file path
            include_metadata: Include failure metadata in export

        Returns:
            Number of jobs exported
        """
        failed_jobs = self.get_failed_jobs(stage=stage)

        if not failed_jobs:
            return 0

        # Build export data
        export_data = []
        for record in failed_jobs:
            job_data = record["job_data"]

            if include_metadata:
                # Add failure metadata to job
                job_data["_failure_metadata"] = {
                    "stage": record["stage"],
                    "error_type": record["error_type"],
                    "error_message": record["error_message"],
                    "failure_count": record["failure_count"],
                    "first_failed": record["first_failed"],
                    "last_failed": record["last_failed"]
                }

            export_data.append(job_data)

        # Write to file
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            return len(export_data)
        except IOError as e:
            print(f"[WARNING] Failed to export failed jobs: {e}")
            return 0

    def get_failure_stats(self) -> Dict[str, Any]:
        """
        Get statistics about failures

        Returns:
            Stats dict with breakdowns by stage and error type
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total failures
        cursor.execute("SELECT COUNT(*) FROM failed_jobs")
        total_failures = cursor.fetchone()[0]

        # By stage
        cursor.execute(
            """
            SELECT stage, COUNT(*) as count
            FROM failed_jobs
            GROUP BY stage
        """
        )
        by_stage = {row[0]: row[1] for row in cursor.fetchall()}

        # By error type
        cursor.execute(
            """
            SELECT error_type, COUNT(*) as count
            FROM failed_jobs
            GROUP BY error_type
        """
        )
        by_error_type = {row[0]: row[1] for row in cursor.fetchall()}

        # Jobs with multiple failures
        cursor.execute(
            "SELECT COUNT(*) FROM failed_jobs WHERE failure_count > 1"
        )
        multiple_failures = cursor.fetchone()[0]

        # Most problematic jobs (highest failure count)
        cursor.execute(
            """
            SELECT job_url, job_title, stage, failure_count
            FROM failed_jobs
            ORDER BY failure_count DESC
            LIMIT 5
        """
        )
        top_failures = [
            {
                "job_url": row[0],
                "job_title": row[1],
                "stage": row[2],
                "failure_count": row[3]
            }
            for row in cursor.fetchall()
        ]

        conn.close()

        return {
            "total_failures": total_failures,
            "by_stage": by_stage,
            "by_error_type": by_error_type,
            "multiple_failures": multiple_failures,
            "top_failures": top_failures
        }

    def get_sample_errors(self, limit: int = 3) -> List[Dict[str, str]]:
        """
        Get sample error messages for display in summary

        Args:
            limit: Maximum number of samples to return

        Returns:
            List of dicts with job_title, error_type, and error_message
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get diverse sample of errors (one per error type)
        cursor.execute(
            """
            SELECT job_title, error_type, error_message, stage
            FROM failed_jobs
            GROUP BY error_type
            LIMIT ?
        """,
            (limit,)
        )

        samples = [
            {
                "job_title": row[0],
                "error_type": row[1],
                "error_message": row[2],
                "stage": row[3]
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return samples

    def clear_stage_failures(self, stage: str) -> int:
        """
        Clear all failures for a specific stage

        Args:
            stage: Pipeline stage

        Returns:
            Number of failures cleared
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM failed_jobs WHERE stage = ?", (stage,))
            removed = cursor.rowcount

            conn.commit()
            conn.close()

            return removed

    def reset(self):
        """Clear all failures (use with caution!)"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM failed_jobs")
            conn.commit()
            conn.close()


if __name__ == "__main__":
    # Test the failure tracker
    print("Testing FailureTracker...")

    tracker = FailureTracker()
    print(f"Database: {tracker.db_path}")

    # Test recording a failure
    sample_job = {
        "job_url": "https://example.com/job/123",
        "title": "Test Job",
        "company": "Test Company",
        "description": "Test description"
    }

    print("\nRecording test failure...")
    success = tracker.record_failure(
        job=sample_job,
        stage="scoring",
        error_type=ErrorType.JSON_PARSE_ERROR,
        error_message="Failed to parse AI response"
    )
    print(f"Recorded: {success}")

    # Record another failure for same job
    print("\nRecording second failure for same job...")
    tracker.record_failure(
        job=sample_job,
        stage="scoring",
        error_type=ErrorType.TIMEOUT_ERROR,
        error_message="Request timed out"
    )

    # Get failed jobs
    print("\nFailed jobs:")
    failed = tracker.get_failed_jobs(stage="scoring")
    for record in failed:
        print(f"  - {record['job_title']} ({record['failure_count']} failures)")
        print(f"    Error: {record['error_type']} - {record['error_message']}")

    # Get stats
    print("\nFailure Statistics:")
    stats = tracker.get_failure_stats()
    print(f"  Total failures: {stats['total_failures']}")
    print(f"  By stage: {stats['by_stage']}")
    print(f"  By error type: {stats['by_error_type']}")
    print(f"  Multiple failures: {stats['multiple_failures']}")

    # Test export
    print("\nExporting failed jobs...")
    export_file = "data/test_failed_jobs.json"
    count = tracker.export_failed_jobs("scoring", export_file)
    print(f"Exported {count} jobs to {export_file}")

    # Test mark resolved
    print("\nMarking job as resolved...")
    resolved = tracker.mark_resolved(sample_job["job_url"], "scoring")
    print(f"Resolved: {resolved}")

    # Verify removal
    print("\nVerifying removal...")
    failed_after = tracker.get_failed_jobs(stage="scoring")
    print(f"Failed jobs remaining: {len(failed_after)}")

    print("\nFailureTracker test complete")
