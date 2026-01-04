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
import threading
import math
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import get_database
from src.utils.profile_manager import ProfilePaths

load_dotenv()


class JobJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for job dicts containing pandas/numpy types"""
    def default(self, obj):
        # Handle pandas Timestamp
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        # Handle datetime
        if isinstance(obj, datetime):
            return obj.isoformat()
        # Handle numpy arrays
        if hasattr(obj, 'tolist'):
            return obj.tolist()
        # Handle numpy scalar types
        if hasattr(obj, 'item'):
            return obj.item()
        # Handle NaN/Infinity
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        return super().default(obj)


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
            db_path: Ignored (kept for compatibility, uses shared DuckDB)
            profile_name: Profile name (default: from .env ACTIVE_PROFILE)
        """
        self.db = get_database(profile_name)
        self.paths = ProfilePaths(profile_name)
        self._lock = threading.Lock()

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

            # Serialize job data as JSON (using custom encoder for Timestamps)
            raw_job_data = json.dumps(job, ensure_ascii=False, cls=JobJSONEncoder)
            now = datetime.now()

            # Check if this job/stage combo already exists
            existing = self.db.fetchone(
                "SELECT failure_count FROM failed_jobs WHERE job_url = ? AND stage = ?",
                (job_url, stage)
            )

            try:
                if existing:
                    # Update existing failure using composite key
                    existing_count = existing[0]
                    self.db.execute("""
                        UPDATE failed_jobs
                        SET error_type = ?,
                            error_message = ?,
                            failure_count = ?,
                            last_failed = ?,
                            raw_job_data = ?
                        WHERE job_url = ? AND stage = ?
                    """, (
                        error_type,
                        error_message,
                        existing_count + 1,
                        now,
                        raw_job_data,
                        job_url,
                        stage
                    ))
                else:
                    # Insert new failure
                    self.db.execute("""
                        INSERT INTO failed_jobs
                        (job_url, job_title, company, stage, error_type,
                         error_message, failure_count, first_failed, last_failed, raw_job_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
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
                    ))

                return True

            except Exception as e:
                print(f"[WARNING] Database error recording failure: {e}")
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
            # Check if exists using composite key
            existing = self.db.fetchone(
                "SELECT job_url FROM failed_jobs WHERE job_url = ? AND stage = ?",
                (job_url, stage)
            )

            if existing:
                self.db.execute(
                    "DELETE FROM failed_jobs WHERE job_url = ? AND stage = ?",
                    (job_url, stage)
                )
                return True

            return False

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
        query = "SELECT * FROM failed_jobs WHERE failure_count >= ?"
        params = [min_failures]

        if stage:
            query += " AND stage = ?"
            params.append(stage)

        if error_type:
            query += " AND error_type = ?"
            params.append(error_type)

        query += " ORDER BY failure_count DESC, last_failed DESC"

        df = self.db.fetchdf(query, tuple(params))

        if df.empty:
            return []

        # Parse raw_job_data JSON
        results = []
        for _, row in df.iterrows():
            record = row.to_dict()
            try:
                record["job_data"] = json.loads(record.get("raw_job_data", "{}"))
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
                    "first_failed": str(record["first_failed"]) if record.get("first_failed") else None,
                    "last_failed": str(record["last_failed"]) if record.get("last_failed") else None,
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
        # Total failures
        result = self.db.fetchone("SELECT COUNT(*) FROM failed_jobs")
        total_failures = result[0] if result else 0

        # By stage
        stage_df = self.db.fetchdf("""
            SELECT stage, COUNT(*) as count
            FROM failed_jobs
            GROUP BY stage
        """)
        by_stage = dict(zip(stage_df["stage"], stage_df["count"])) if not stage_df.empty else {}

        # By error type
        error_df = self.db.fetchdf("""
            SELECT error_type, COUNT(*) as count
            FROM failed_jobs
            GROUP BY error_type
        """)
        by_error_type = dict(zip(error_df["error_type"], error_df["count"])) if not error_df.empty else {}

        # Jobs with multiple failures
        result = self.db.fetchone(
            "SELECT COUNT(*) FROM failed_jobs WHERE failure_count > 1"
        )
        multiple_failures = result[0] if result else 0

        # Most problematic jobs (highest failure count)
        top_df = self.db.fetchdf("""
            SELECT job_url, job_title, stage, failure_count
            FROM failed_jobs
            ORDER BY failure_count DESC
            LIMIT 5
        """)
        top_failures = top_df.to_dict("records") if not top_df.empty else []

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
        df = self.db.fetchdf(f"""
            SELECT job_title, error_type, error_message, stage
            FROM failed_jobs
            GROUP BY error_type
            LIMIT {limit}
        """)

        if df.empty:
            return []

        return df.to_dict("records")

    def clear_stage_failures(self, stage: str) -> int:
        """
        Clear all failures for a specific stage

        Args:
            stage: Pipeline stage

        Returns:
            Number of failures cleared
        """
        with self._lock:
            # Get count first
            result = self.db.fetchone(
                "SELECT COUNT(*) FROM failed_jobs WHERE stage = ?",
                (stage,)
            )
            count = result[0] if result else 0

            self.db.execute("DELETE FROM failed_jobs WHERE stage = ?", (stage,))

            return count

    def reset(self):
        """Clear all failures (use with caution!)"""
        with self._lock:
            self.db.execute("DELETE FROM failed_jobs")


if __name__ == "__main__":
    # Test the failure tracker
    print("Testing FailureTracker...")

    tracker = FailureTracker()
    print(f"Database: {tracker.db.db_path}")

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

    # Test mark resolved
    print("\nMarking job as resolved...")
    resolved = tracker.mark_resolved(sample_job["job_url"], "scoring")
    print(f"Resolved: {resolved}")

    # Verify removal
    print("\nVerifying removal...")
    failed_after = tracker.get_failed_jobs(stage="scoring")
    print(f"Failed jobs remaining: {len(failed_after)}")

    print("\nFailureTracker test complete")
