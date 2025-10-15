"""
Job Tracker Tools

Tools for querying job tracking database and statistics.
"""

import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.profile_manager import ProfilePaths
from .base import tracker_registry, BaseTool
from ..utils.response_formatter import format_success_response


class TrackerStatsTool(BaseTool):
    """Show job tracker statistics"""

    def __init__(self):
        super().__init__("stats", "Show job tracker statistics")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        from job_matcher.job_tracker import JobTracker

        paths = ProfilePaths()

        if not paths.job_tracker_db.exists():
            return format_success_response(
                data={"total_jobs": 0},
                message="No jobs tracked yet",
            )

        tracker = JobTracker(str(paths.job_tracker_db))
        stats = tracker.get_stats()

        return format_success_response({
            "statistics": stats,
            "database": str(paths.job_tracker_db),
        })


class TrackerFailuresTool(BaseTool):
    """Show failure statistics"""

    def __init__(self):
        super().__init__("failures", "Show job processing failure statistics")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        from job_matcher.failure_tracker import FailureTracker

        paths = ProfilePaths()

        if not paths.failure_tracker_db.exists():
            return format_success_response(
                data={"total_failures": 0},
                message="No failures tracked",
            )

        tracker = FailureTracker(str(paths.failure_tracker_db))
        stats = tracker.get_all_failure_statistics()

        return format_success_response({
            "failure_statistics": stats,
            "database": str(paths.failure_tracker_db),
        })


# Register tools
tracker_registry.register("stats", TrackerStatsTool())
tracker_registry.register("failures", TrackerFailuresTool())


async def execute(tool_action: str, parameters: Dict[str, Any]) -> Any:
    """Execute a tracker tool"""
    tool = tracker_registry.get(tool_action)
    if not tool:
        raise ValueError(f"Unknown tracker tool: {tool_action}")
    return await tool.execute(**parameters)
