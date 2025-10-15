"""
Job Data Resources

Provides access to scraped and matched job data.

URI Format: jobs://{data_type}/{source}/{version}

Examples:
  - jobs://scraped/indeed/latest
  - jobs://matched/glassdoor/latest
  - jobs://tracked/default
  - jobs://failed/default
"""

import sys
import json
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.profile_manager import ProfilePaths


async def get(path: str, current_user: dict) -> Dict[str, Any]:
    """
    Get job data resource

    Args:
        path: Resource path
        current_user: Current user context

    Returns:
        Job data
    """
    parts = path.split("/")

    if len(parts) < 2:
        raise ValueError(f"Invalid job resource path: {path}")

    data_type = parts[0]

    if data_type == "scraped":
        return await _get_scraped_jobs(parts[1:])
    elif data_type == "matched":
        return await _get_matched_jobs(parts[1:])
    elif data_type == "tracked":
        return await _get_tracked_jobs(parts[1] if len(parts) > 1 else "default")
    elif data_type == "failed":
        return await _get_failed_jobs(parts[1] if len(parts) > 1 else "default")
    else:
        raise ValueError(f"Unknown job data type: {data_type}")


async def _get_scraped_jobs(parts: list) -> Dict[str, Any]:
    """Get scraped jobs data"""
    if len(parts) < 2:
        raise ValueError("Expected format: jobs://scraped/{source}/{version}")

    source = parts[0]
    version = parts[1]

    paths = ProfilePaths()

    if version == "latest":
        job_file = paths.data_dir / f"jobs_{source}_latest.json"
    else:
        job_file = paths.data_dir / f"jobs_{source}_{version}.json"

    if not job_file.exists():
        raise FileNotFoundError(f"Job data not found: {job_file}")

    with open(job_file, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    return {
        "data": {
            "source": source,
            "version": version,
            "file_path": str(job_file),
            "jobs": jobs,
            "count": len(jobs) if isinstance(jobs, list) else 1,
        },
        "content_type": "application/json",
    }


async def _get_matched_jobs(parts: list) -> Dict[str, Any]:
    """Get matched jobs data"""
    if len(parts) < 2:
        raise ValueError("Expected format: jobs://matched/{source}/{version}")

    source = parts[0]
    version = parts[1]

    paths = ProfilePaths()

    if version == "latest":
        # Find most recent matched file
        matched_files = list(paths.data_dir.glob(f"jobs_{source}_matched_*.json"))
        if not matched_files:
            raise FileNotFoundError(f"No matched jobs found for source: {source}")

        job_file = max(matched_files, key=lambda p: p.stat().st_mtime)
    else:
        job_file = paths.data_dir / f"jobs_{source}_matched_{version}.json"

    if not job_file.exists():
        raise FileNotFoundError(f"Matched job data not found: {job_file}")

    with open(job_file, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    return {
        "data": {
            "source": source,
            "version": version,
            "file_path": str(job_file),
            "jobs": jobs,
            "count": len(jobs) if isinstance(jobs, list) else 1,
        },
        "content_type": "application/json",
    }


async def _get_tracked_jobs(profile_name: str) -> Dict[str, Any]:
    """Get tracked jobs from database"""
    paths = ProfilePaths(profile_name)

    if not paths.job_tracker_db.exists():
        return {
            "data": {
                "tracked_jobs": [],
                "count": 0,
                "message": "No jobs tracked yet",
            },
            "content_type": "application/json",
        }

    from job_matcher.job_tracker import JobTracker

    tracker = JobTracker(str(paths.job_tracker_db))
    stats = tracker.get_stats()

    return {
        "data": {
            "database_path": str(paths.job_tracker_db),
            "statistics": stats,
            "profile": profile_name,
        },
        "content_type": "application/json",
    }


async def _get_failed_jobs(profile_name: str) -> Dict[str, Any]:
    """Get failed jobs from database"""
    paths = ProfilePaths(profile_name)

    if not paths.failure_tracker_db.exists():
        return {
            "data": {
                "failed_jobs": [],
                "count": 0,
                "message": "No failures tracked",
            },
            "content_type": "application/json",
        }

    from job_matcher.failure_tracker import FailureTracker

    tracker = FailureTracker(str(paths.failure_tracker_db))
    stats = tracker.get_all_failure_statistics()

    return {
        "data": {
            "database_path": str(paths.failure_tracker_db),
            "statistics": stats,
            "profile": profile_name,
        },
        "content_type": "application/json",
    }
