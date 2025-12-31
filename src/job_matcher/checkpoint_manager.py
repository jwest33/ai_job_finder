"""
CheckpointManager - Pipeline State Management

Provides checkpoint/resume functionality for the job matcher pipeline,
allowing long-running processes to be interrupted and resumed without
losing progress.

Thread-safe for multi-threaded job processing.
"""

import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import get_database
from src.utils.profile_manager import ProfilePaths


class CheckpointManager:
    """Manages checkpoint state for resume-able pipeline execution (thread-safe)"""

    def __init__(self, checkpoint_dir: Optional[str] = None, profile_name: Optional[str] = None):
        """
        Initialize CheckpointManager

        Args:
            checkpoint_dir: Ignored (kept for compatibility)
            profile_name: Profile name (default: from .env ACTIVE_PROFILE)
        """
        self.db = get_database(profile_name)
        self.paths = ProfilePaths(profile_name)
        self.checkpoint_data = None
        self._checkpoint_source = None
        self._lock = threading.Lock()

    def has_checkpoint(self, input_file: str) -> bool:
        """
        Check if a checkpoint exists for the given input file

        Args:
            input_file: Path to input jobs file (or source identifier)

        Returns:
            True if checkpoint exists and matches input file
        """
        result = self.db.fetchone(
            "SELECT source FROM checkpoints WHERE source = ? AND is_active = TRUE",
            (input_file,)
        )
        return result is not None

    def load_checkpoint(self, input_file: str) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint data if it exists and matches the input file

        Args:
            input_file: Path to input jobs file (or source identifier)

        Returns:
            Checkpoint data dict or None if no valid checkpoint
        """
        result = self.db.fetchone(
            """SELECT source, min_score, stage, processed_urls, matched_jobs_data,
                      created_at, updated_at
               FROM checkpoints WHERE source = ? AND is_active = TRUE""",
            (input_file,)
        )

        if not result:
            return None

        self._checkpoint_source = result[0]  # Use source as the key

        # Parse stored JSON data
        try:
            processed_urls_data = json.loads(result[3]) if result[3] else {}
            matched_jobs_data = json.loads(result[4]) if result[4] else {}
        except json.JSONDecodeError:
            processed_urls_data = {}
            matched_jobs_data = {}

        self.checkpoint_data = {
            "input_file": result[0],
            "timestamp": str(result[5]) if result[5] else datetime.now().isoformat(),
            "min_score": result[1] or 0,
            "stages": processed_urls_data.get("stages", {
                "scoring": {"completed": False, "processed_urls": [], "processed_count": 0, "matched_count": 0},
                "analysis": {"completed": False, "processed_urls": [], "processed_count": 0},
                "optimization": {"completed": False, "processed_urls": [], "processed_count": 0}
            }),
            "output_files": processed_urls_data.get("output_files", {}),
            "matched_jobs": matched_jobs_data
        }

        return self.checkpoint_data

    def create_checkpoint(
        self,
        input_file: str,
        min_score: int,
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new checkpoint

        Args:
            input_file: Path to input jobs file (or source identifier)
            min_score: Minimum match score threshold
            output_file: Optional path to matched jobs output file

        Returns:
            New checkpoint data dict
        """
        now = datetime.now()

        self.checkpoint_data = {
            "input_file": input_file,
            "timestamp": now.isoformat(),
            "min_score": min_score,
            "stages": {
                "scoring": {
                    "completed": False,
                    "processed_urls": [],
                    "processed_count": 0,
                    "matched_count": 0
                },
                "analysis": {
                    "completed": False,
                    "processed_urls": [],
                    "processed_count": 0
                },
                "optimization": {
                    "completed": False,
                    "processed_urls": [],
                    "processed_count": 0
                }
            },
            "output_files": {
                "matched_jobs": output_file
            },
            "matched_jobs": {}
        }

        # Deactivate any existing checkpoints for this source
        self.db.execute(
            "UPDATE checkpoints SET is_active = FALSE WHERE source = ?",
            (input_file,)
        )

        # Create new checkpoint
        self.db.execute("""
            INSERT INTO checkpoints (source, min_score, stage, processed_urls,
                                     matched_jobs_data, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, TRUE, ?, ?)
        """, (
            input_file,
            min_score,
            "scoring",
            json.dumps({"stages": self.checkpoint_data["stages"],
                       "output_files": self.checkpoint_data["output_files"]}),
            json.dumps({}),
            now,
            now
        ))

        # Store the source as our checkpoint key
        self._checkpoint_source = input_file

        return self.checkpoint_data

    def _save(self):
        """Save checkpoint data to database"""
        if not self.checkpoint_data or not self._checkpoint_source:
            return

        now = datetime.now()

        # Determine current stage
        current_stage = "scoring"
        if self.checkpoint_data["stages"]["scoring"]["completed"]:
            current_stage = "analysis"
        if self.checkpoint_data["stages"]["analysis"]["completed"]:
            current_stage = "optimization"

        self.db.execute("""
            UPDATE checkpoints SET
                min_score = ?,
                stage = ?,
                processed_urls = ?,
                matched_jobs_data = ?,
                updated_at = ?
            WHERE source = ?
        """, (
            self.checkpoint_data.get("min_score", 0),
            current_stage,
            json.dumps({"stages": self.checkpoint_data["stages"],
                       "output_files": self.checkpoint_data.get("output_files", {})}),
            json.dumps(self.checkpoint_data.get("matched_jobs", {})),
            now,
            self._checkpoint_source
        ))

    def mark_job_completed(self, stage: str, job_url: str):
        """
        Mark a job as completed for a specific stage (thread-safe)

        Args:
            stage: Pipeline stage (scoring, analysis, optimization)
            job_url: Job URL identifier
        """
        if not self.checkpoint_data:
            return

        with self._lock:
            if stage not in self.checkpoint_data["stages"]:
                print(f"[WARNING] Invalid stage: {stage}")
                return

            stage_data = self.checkpoint_data["stages"][stage]

            # Add URL if not already present
            if job_url not in stage_data["processed_urls"]:
                stage_data["processed_urls"].append(job_url)
                stage_data["processed_count"] = len(stage_data["processed_urls"])
                self._save()

    def mark_stage_completed(self, stage: str, matched_count: Optional[int] = None):
        """
        Mark a pipeline stage as fully completed (thread-safe)

        Args:
            stage: Pipeline stage (scoring, analysis, optimization)
            matched_count: Optional count of matched jobs (for scoring stage)
        """
        if not self.checkpoint_data:
            return

        with self._lock:
            if stage not in self.checkpoint_data["stages"]:
                print(f"[WARNING] Invalid stage: {stage}")
                return

            self.checkpoint_data["stages"][stage]["completed"] = True

            if matched_count is not None:
                self.checkpoint_data["stages"][stage]["matched_count"] = matched_count

            self._save()

    def update_output_file(self, file_type: str, file_path: str):
        """
        Update output file path in checkpoint (thread-safe)

        Args:
            file_type: Type of output file (e.g., 'matched_jobs')
            file_path: Path to output file
        """
        if not self.checkpoint_data:
            return

        with self._lock:
            if "output_files" not in self.checkpoint_data:
                self.checkpoint_data["output_files"] = {}
            self.checkpoint_data["output_files"][file_type] = file_path
            self._save()

    def save_matched_job(self, job_url: str, job_data: Dict[str, Any]):
        """
        Save a matched job's data to checkpoint for resume

        Args:
            job_url: Job URL identifier
            job_data: Full job data with match results
        """
        if not self.checkpoint_data:
            return

        with self._lock:
            if "matched_jobs" not in self.checkpoint_data:
                self.checkpoint_data["matched_jobs"] = {}
            self.checkpoint_data["matched_jobs"][job_url] = job_data
            self._save()

    def get_matched_jobs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all matched jobs from checkpoint

        Returns:
            Dict mapping job URLs to job data
        """
        if not self.checkpoint_data:
            return {}
        return self.checkpoint_data.get("matched_jobs", {})

    def get_processed_urls(self, stage: str) -> List[str]:
        """
        Get list of URLs already processed for a stage

        Args:
            stage: Pipeline stage (scoring, analysis, optimization)

        Returns:
            List of processed job URLs
        """
        if not self.checkpoint_data:
            return []

        if stage not in self.checkpoint_data["stages"]:
            return []

        return self.checkpoint_data["stages"][stage].get("processed_urls", [])

    def is_stage_completed(self, stage: str) -> bool:
        """
        Check if a pipeline stage is completed

        Args:
            stage: Pipeline stage (scoring, analysis, optimization)

        Returns:
            True if stage is completed
        """
        if not self.checkpoint_data:
            return False

        if stage not in self.checkpoint_data["stages"]:
            return False

        return self.checkpoint_data["stages"][stage].get("completed", False)

    def get_stage_stats(self, stage: str) -> Dict[str, Any]:
        """
        Get statistics for a pipeline stage

        Args:
            stage: Pipeline stage (scoring, analysis, optimization)

        Returns:
            Dict with stage statistics
        """
        if not self.checkpoint_data:
            return {"processed_count": 0, "completed": False}

        if stage not in self.checkpoint_data["stages"]:
            return {"processed_count": 0, "completed": False}

        stage_data = self.checkpoint_data["stages"][stage]
        return {
            "processed_count": stage_data.get("processed_count", 0),
            "completed": stage_data.get("completed", False),
            "matched_count": stage_data.get("matched_count", 0)
        }

    def get_output_file(self, file_type: str) -> Optional[str]:
        """
        Get path to output file from checkpoint

        Args:
            file_type: Type of output file (e.g., 'matched_jobs')

        Returns:
            Path to output file or None
        """
        if not self.checkpoint_data:
            return None

        return self.checkpoint_data.get("output_files", {}).get(file_type)

    def remove_urls_from_checkpoint(self, urls: List[str], stage: Optional[str] = None):
        """
        Remove specific URLs from checkpoint (for reprocessing)

        Args:
            urls: List of job URLs to remove
            stage: Specific stage to remove from, or None for all stages
        """
        if not self.checkpoint_data:
            return

        with self._lock:
            stages_to_clear = [stage] if stage else ["scoring", "analysis", "optimization"]

            for stage_name in stages_to_clear:
                if stage_name not in self.checkpoint_data["stages"]:
                    continue

                stage_data = self.checkpoint_data["stages"][stage_name]

                # Remove URLs from processed list
                original_count = len(stage_data["processed_urls"])
                stage_data["processed_urls"] = [
                    url for url in stage_data["processed_urls"] if url not in urls
                ]
                removed_count = original_count - len(stage_data["processed_urls"])

                # Update processed count
                stage_data["processed_count"] = len(stage_data["processed_urls"])

                # Mark stage as incomplete if we removed URLs
                if removed_count > 0:
                    stage_data["completed"] = False

            self._save()

    def clear_checkpoint(self):
        """Remove the active checkpoint"""
        if self._checkpoint_source:
            self.db.execute(
                "DELETE FROM checkpoints WHERE source = ?",
                (self._checkpoint_source,)
            )
            print("Checkpoint cleared")

        self.checkpoint_data = None
        self._checkpoint_source = None

    def get_summary(self) -> str:
        """
        Get a human-readable summary of checkpoint status

        Returns:
            Summary string
        """
        if not self.checkpoint_data:
            return "No checkpoint data"

        timestamp = self.checkpoint_data.get("timestamp", "Unknown")
        input_file = self.checkpoint_data.get("input_file", "Unknown")
        min_score = self.checkpoint_data.get("min_score", 0)

        scoring_stats = self.get_stage_stats("scoring")
        analysis_stats = self.get_stage_stats("analysis")
        optimization_stats = self.get_stage_stats("optimization")

        summary = f"""Checkpoint Summary:
  Input: {input_file}
  Created: {timestamp}
  Min Score: {min_score}

  Progress:
    Scoring: {scoring_stats['processed_count']} jobs {'Complete' if scoring_stats['completed'] else '[INFO] In Progress'}
    Analysis: {analysis_stats['processed_count']} jobs {'Complete' if analysis_stats['completed'] else '[INFO] In Progress'}
    Optimization: {optimization_stats['processed_count']} jobs {'Complete' if optimization_stats['completed'] else '[INFO] In Progress'}"""

        return summary


if __name__ == "__main__":
    # Test the checkpoint manager
    print("Testing CheckpointManager...")

    manager = CheckpointManager()

    # Create a test checkpoint
    print("\nCreating checkpoint...")
    checkpoint = manager.create_checkpoint(
        input_file="glassdoor",
        min_score=70,
        output_file="data/jobs_matched_test.json"
    )
    print("Checkpoint created")

    # Mark some jobs as processed
    print("\nMarking jobs as processed...")
    manager.mark_job_completed("scoring", "https://example.com/job1")
    manager.mark_job_completed("scoring", "https://example.com/job2")
    manager.mark_job_completed("scoring", "https://example.com/job3")
    print("Jobs marked")

    # Get stats
    print("\nCheckpoint summary:")
    print(manager.get_summary())

    # Test loading
    print("\nLoading checkpoint...")
    manager2 = CheckpointManager()
    loaded = manager2.load_checkpoint("glassdoor")
    if loaded:
        print("Checkpoint loaded successfully")
        print(f"   Processed URLs: {manager2.get_processed_urls('scoring')}")
    else:
        print("X Failed to load checkpoint")

    # Clear checkpoint
    print("\nClearing checkpoint...")
    manager.clear_checkpoint()

    print("\nCheckpointManager test complete")
