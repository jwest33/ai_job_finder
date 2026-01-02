"""
PendingWriteManager - Fallback for failed database writes

When batch database writes fail (due to lock contention, corruption, etc.),
this module saves the records to JSON files for later retry. On startup,
pending files are processed and deleted upon successful insertion.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.profile_manager import ProfilePaths


class PendingWriteManager:
    """Manages pending database writes that failed and need retry."""

    def __init__(self, profile_name: Optional[str] = None):
        """
        Initialize PendingWriteManager.

        Args:
            profile_name: Profile name (default: from .env ACTIVE_PROFILE)
        """
        self.paths = ProfilePaths(profile_name)
        self.pending_dir = self.paths.data_dir / "pending"

    def save_pending(
        self,
        records: List[Dict[str, Any]],
        operation: str,
        source: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Save failed records to a pending file for later retry.

        Args:
            records: List of record dicts that failed to save
            operation: Operation type ('save_jobs', 'update_match_results', etc.)
            source: Optional source identifier (e.g., 'indeed', 'glassdoor')

        Returns:
            Path to saved pending file, or None if no records
        """
        if not records:
            return None

        # Ensure pending directory exists
        self.pending_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        source_part = f"_{source}" if source else ""
        filename = f"pending_{operation}{source_part}_{timestamp}.json"
        filepath = self.pending_dir / filename

        # Prepare data with metadata
        pending_data = {
            "operation": operation,
            "source": source,
            "created_at": datetime.now().isoformat(),
            "record_count": len(records),
            "records": records,
        }

        # Convert any remaining non-serializable objects
        def convert_value(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            elif hasattr(obj, 'tolist'):  # numpy arrays
                return obj.tolist()
            elif hasattr(obj, '__dict__'):
                return obj.__dict__
            return str(obj)

        def make_serializable(data):
            if isinstance(data, dict):
                return {k: make_serializable(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [make_serializable(item) for item in data]
            else:
                try:
                    json.dumps(data)
                    return data
                except (TypeError, ValueError):
                    return convert_value(data)

        serializable_data = make_serializable(pending_data)

        # Write to file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(serializable_data, f, indent=2, ensure_ascii=False)

        print(f"[WARNING] Saved {len(records)} pending {operation} records to: {filepath}")
        return filepath

    def get_pending_files(self) -> List[Path]:
        """
        Get all pending files in order of creation (oldest first).

        Returns:
            List of pending file paths
        """
        if not self.pending_dir.exists():
            return []

        pending_files = list(self.pending_dir.glob("pending_*.json"))
        # Sort by modification time (oldest first for FIFO processing)
        return sorted(pending_files, key=lambda p: p.stat().st_mtime)

    def process_pending(self, storage=None) -> Dict[str, int]:
        """
        Process all pending files, attempting to insert records.

        Args:
            storage: Optional JobStorage instance (will import if not provided)

        Returns:
            Dict with counts: {"processed": N, "failed": M, "deleted": K}
        """
        pending_files = self.get_pending_files()
        if not pending_files:
            return {"processed": 0, "failed": 0, "deleted": 0}

        # Import storage if not provided
        if storage is None:
            from src.core.storage import JobStorage
            storage = JobStorage(profile_name=self.paths.profile_name)

        results = {"processed": 0, "failed": 0, "deleted": 0}

        for filepath in pending_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    pending_data = json.load(f)

                operation = pending_data.get("operation", "unknown")
                source = pending_data.get("source")
                records = pending_data.get("records", [])

                if not records:
                    # Empty file, delete it
                    filepath.unlink()
                    results["deleted"] += 1
                    continue

                # Try to process based on operation type
                success = self._try_insert(storage, operation, records, source)

                if success:
                    # Delete the pending file on success
                    filepath.unlink()
                    results["processed"] += len(records)
                    results["deleted"] += 1
                    print(f"[SUCCESS] Processed {len(records)} pending {operation} records from: {filepath.name}")
                else:
                    results["failed"] += len(records)
                    print(f"[WARNING] Failed to process pending file: {filepath.name}")

            except Exception as e:
                print(f"[ERROR] Error processing pending file {filepath}: {e}")
                results["failed"] += 1

        return results

    def _try_insert(
        self,
        storage,
        operation: str,
        records: List[Dict[str, Any]],
        source: Optional[str],
    ) -> bool:
        """
        Attempt to insert pending records.

        Args:
            storage: JobStorage instance
            operation: Operation type
            records: Records to insert
            source: Source identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            if operation == "save_jobs":
                # Convert dicts back to JobPost objects
                from src.core.models import JobPost
                jobs = []
                for record in records:
                    try:
                        job = JobPost(**record)
                        jobs.append(job)
                    except Exception:
                        # Skip invalid records
                        continue

                if jobs:
                    # Use the regular save_jobs method (not batch, to avoid recursion)
                    storage.save_jobs(jobs, source=source or "unknown")
                return True

            elif operation == "update_match_results":
                # Update match results one by one (fallback)
                for record in records:
                    try:
                        storage.update_match_results(
                            job_url=record.get("job_url", ""),
                            match_score=record.get("match_score"),
                            match_explanation=record.get("match_explanation"),
                            is_relevant=record.get("is_relevant"),
                            gap_analysis=record.get("gap_analysis"),
                            resume_suggestions=record.get("resume_suggestions"),
                        )
                    except Exception:
                        continue
                return True

            elif operation == "add_jobs_tracker":
                # Tracker updates
                from src.job_matcher.job_tracker import JobTracker
                tracker = JobTracker(profile_name=self.paths.profile_name)
                for record in records:
                    try:
                        tracker.add_job(
                            job_url=record.get("job_url", ""),
                            job_title=record.get("title", "Unknown"),
                            company=record.get("company", "Unknown"),
                            location=record.get("location", "Unknown"),
                            match_score=record.get("match_score", 0),
                        )
                    except Exception:
                        continue
                return True

            else:
                print(f"[WARNING] Unknown operation type: {operation}")
                return False

        except Exception as e:
            print(f"[ERROR] Failed to insert pending records: {e}")
            return False

    def clear_pending(self) -> int:
        """
        Clear all pending files (use with caution!).

        Returns:
            Number of files deleted
        """
        pending_files = self.get_pending_files()
        count = 0
        for filepath in pending_files:
            try:
                filepath.unlink()
                count += 1
            except Exception:
                pass
        return count

    def get_pending_stats(self) -> Dict[str, Any]:
        """
        Get statistics about pending files.

        Returns:
            Dict with stats: file_count, total_records, operations, oldest_file
        """
        pending_files = self.get_pending_files()
        if not pending_files:
            return {
                "file_count": 0,
                "total_records": 0,
                "operations": {},
                "oldest_file": None,
            }

        total_records = 0
        operations = {}

        for filepath in pending_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    record_count = data.get("record_count", 0)
                    operation = data.get("operation", "unknown")

                    total_records += record_count
                    operations[operation] = operations.get(operation, 0) + record_count
            except Exception:
                pass

        oldest_file = pending_files[0].name if pending_files else None

        return {
            "file_count": len(pending_files),
            "total_records": total_records,
            "operations": operations,
            "oldest_file": oldest_file,
        }


def get_pending_manager(profile_name: Optional[str] = None) -> PendingWriteManager:
    """
    Get PendingWriteManager instance for a profile.

    Args:
        profile_name: Profile name (default: from .env ACTIVE_PROFILE)

    Returns:
        PendingWriteManager instance
    """
    return PendingWriteManager(profile_name)


if __name__ == "__main__":
    # Test the pending write manager
    print("Testing PendingWriteManager...")

    manager = get_pending_manager()
    print(f"Pending directory: {manager.pending_dir}")

    # Get stats
    stats = manager.get_pending_stats()
    print(f"\nPending Stats:")
    print(f"  Files: {stats['file_count']}")
    print(f"  Total records: {stats['total_records']}")
    print(f"  Operations: {stats['operations']}")
    print(f"  Oldest file: {stats['oldest_file']}")

    # Test saving a pending record
    test_records = [
        {"job_url": "https://example.com/job/1", "title": "Test Job", "company": "Test Co"},
        {"job_url": "https://example.com/job/2", "title": "Test Job 2", "company": "Test Co 2"},
    ]

    print("\nSaving test pending records...")
    filepath = manager.save_pending(test_records, "test_operation", "test_source")
    print(f"Saved to: {filepath}")

    # Check stats again
    stats = manager.get_pending_stats()
    print(f"\nUpdated Stats:")
    print(f"  Files: {stats['file_count']}")
    print(f"  Total records: {stats['total_records']}")

    print("\nPendingWriteManager test complete")
