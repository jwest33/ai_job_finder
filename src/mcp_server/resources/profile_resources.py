"""
Profile Resources

Provides read-only access to profile data and configuration.

URI Format: profile://{profile_name}/{resource_type}

Examples:
  - profile://default/config
  - profile://default/resume
  - profile://default/requirements
  - profile://ai-engineer/tracker
"""

import sys
import json
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.profile_manager import ProfileManager, ProfilePaths


async def get(path: str, current_user: dict) -> Dict[str, Any]:
    """
    Get profile resource

    Args:
        path: Resource path (e.g., "default/config", "ai-engineer/resume")
        current_user: Current user context

    Returns:
        Resource data with content_type

    Raises:
        ValueError: If path is invalid
        FileNotFoundError: If resource doesn't exist
    """
    parts = path.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid profile resource path: {path}. Expected format: {{profile_name}}/{{resource_type}}")

    profile_name, resource_type = parts

    manager = ProfileManager()

    # Check if profile exists
    if not manager.profile_exists(profile_name):
        raise FileNotFoundError(f"Profile '{profile_name}' does not exist")

    paths = ProfilePaths(profile_name)

    # Handle different resource types
    if resource_type == "config":
        return await _get_profile_config(manager, profile_name)

    elif resource_type == "resume":
        return await _get_resume(paths)

    elif resource_type == "requirements":
        return await _get_requirements(paths)

    elif resource_type == "tracker":
        return await _get_tracker_info(paths)

    elif resource_type == "reports":
        return await _get_reports_list(paths)

    else:
        raise ValueError(f"Unknown resource type: {resource_type}")


async def _get_profile_config(manager: ProfileManager, profile_name: str) -> Dict[str, Any]:
    """Get profile configuration"""
    info = manager.get_profile_info(profile_name)
    email_config = manager.get_profile_email_config(profile_name)

    if email_config:
        info["email_config"] = email_config

    return {
        "data": info,
        "content_type": "application/json",
    }


async def _get_resume(paths: ProfilePaths) -> Dict[str, Any]:
    """Get resume content"""
    if not paths.resume_path.exists():
        raise FileNotFoundError(f"Resume not found: {paths.resume_path}")

    with open(paths.resume_path, "r", encoding="utf-8") as f:
        content = f.read()

    return {
        "data": {
            "path": str(paths.resume_path),
            "content": content,
            "size_bytes": len(content),
            "lines": len(content.split("\n")),
        },
        "content_type": "text/plain",
    }


async def _get_requirements(paths: ProfilePaths) -> Dict[str, Any]:
    """Get requirements YAML content"""
    import yaml

    if not paths.requirements_path.exists():
        raise FileNotFoundError(f"Requirements not found: {paths.requirements_path}")

    with open(paths.requirements_path, "r", encoding="utf-8") as f:
        content = f.read()
        data = yaml.safe_load(content)

    return {
        "data": {
            "path": str(paths.requirements_path),
            "content": content,
            "parsed": data,
        },
        "content_type": "application/yaml",
    }


async def _get_tracker_info(paths: ProfilePaths) -> Dict[str, Any]:
    """Get job tracker information"""
    if not paths.job_tracker_db.exists():
        return {
            "data": {
                "exists": False,
                "message": "No jobs tracked yet",
            },
            "content_type": "application/json",
        }

    from job_matcher.job_tracker import JobTracker

    tracker = JobTracker(str(paths.job_tracker_db))
    stats = tracker.get_stats()

    return {
        "data": {
            "exists": True,
            "database_path": str(paths.job_tracker_db),
            "statistics": stats,
        },
        "content_type": "application/json",
    }


async def _get_reports_list(paths: ProfilePaths) -> Dict[str, Any]:
    """Get list of HTML reports"""
    if not paths.reports_dir.exists():
        return {
            "data": {"reports": [], "count": 0},
            "content_type": "application/json",
        }

    reports = []
    for report_file in paths.reports_dir.glob("*.html"):
        stat = report_file.stat()
        reports.append({
            "filename": report_file.name,
            "path": str(report_file),
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
        })

    # Sort by modified time (newest first)
    reports.sort(key=lambda r: r["modified"], reverse=True)

    return {
        "data": {
            "reports": reports,
            "count": len(reports),
            "directory": str(paths.reports_dir),
        },
        "content_type": "application/json",
    }
