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

# Add parent directory to path for profile_manager import
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.profile_manager import ProfilePaths


class CheckpointManager:
    """Manages checkpoint state for resume-able pipeline execution (thread-safe)"""

    def __init__(self, checkpoint_dir: Optional[str] = None, profile_name: Optional[str] = None):
        """
        Initialize CheckpointManager

        Args:
            checkpoint_dir: Directory to store checkpoint files (default: from profile)
            profile_name: Profile name (default: from .env ACTIVE_PROFILE)
        """
        # Get profile paths
        paths = ProfilePaths(profile_name)

        # Use profile data directory as default, or custom dir if provided
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else paths.data_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.active_checkpoint_file = self.checkpoint_dir / ".checkpoint_active.json"
        self.checkpoint_data = None
        self._lock = threading.Lock()  # Thread-safe operations

    def has_checkpoint(self, input_file: str) -> bool:
        """
        Check if a checkpoint exists for the given input file

        Args:
            input_file: Path to input jobs file

        Returns:
            True if checkpoint exists and matches input file
        """
        if not self.active_checkpoint_file.exists():
            return False

        try:
            with open(self.active_checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("input_file") == input_file
        except (json.JSONDecodeError, IOError):
            return False

    def load_checkpoint(self, input_file: str) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint data if it exists and matches the input file

        Args:
            input_file: Path to input jobs file

        Returns:
            Checkpoint data dict or None if no valid checkpoint
        """
        if not self.has_checkpoint(input_file):
            return None

        try:
            with open(self.active_checkpoint_file, "r", encoding="utf-8") as f:
                self.checkpoint_data = json.load(f)
                return self.checkpoint_data
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARNING] Failed to load checkpoint: {e}")
            return None

    def create_checkpoint(
        self,
        input_file: str,
        min_score: int,
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new checkpoint

        Args:
            input_file: Path to input jobs file
            min_score: Minimum match score threshold
            output_file: Optional path to matched jobs output file

        Returns:
            New checkpoint data dict
        """
        self.checkpoint_data = {
            "input_file": input_file,
            "timestamp": datetime.now().isoformat(),
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
            }
        }
        self._save()
        return self.checkpoint_data

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
            self.checkpoint_data["output_files"][file_type] = file_path
            self._save()

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

        return self.checkpoint_data["output_files"].get(file_type)

    def clear_checkpoint(self):
        """Remove the active checkpoint file"""
        if self.active_checkpoint_file.exists():
            try:
                self.active_checkpoint_file.unlink()
                print("Checkpoint cleared")
            except OSError as e:
                print(f"[WARNING] Failed to clear checkpoint: {e}")

        self.checkpoint_data = None

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

    def _save(self):
        """Save checkpoint data to disk"""
        if not self.checkpoint_data:
            return

        try:
            with open(self.active_checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(self.checkpoint_data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"[WARNING] Failed to save checkpoint: {e}")


if __name__ == "__main__":
    # Test the checkpoint manager
    print("Testing CheckpointManager...")

    manager = CheckpointManager()

    # Create a test checkpoint
    print("\nCreating checkpoint...")
    checkpoint = manager.create_checkpoint(
        input_file="data/jobs_latest.json",
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
    loaded = manager2.load_checkpoint("data/jobs_latest.json")
    if loaded:
        print("Checkpoint loaded successfully")
        print(f"   Processed URLs: {manager2.get_processed_urls('scoring')}")
    else:
        print("X Failed to load checkpoint")

    # Clear checkpoint
    print("\nClearing checkpoint...")
    manager.clear_checkpoint()

    print("\nCheckpointManager test complete")
