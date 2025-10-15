"""
Profile Management Tools

Tools for managing job search profiles including create, switch, delete, and query operations.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.profile_manager import ProfileManager, ProfilePaths
from .base import profile_registry, BaseTool
from ..utils.response_formatter import format_success_response, format_error_response
from ..utils.error_handler import ProfileNotFoundError


class ProfileListTool(BaseTool):
    """List all available profiles"""

    def __init__(self):
        super().__init__("list", "List all available profiles")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        manager = ProfileManager()
        profiles = manager.list_profiles()
        active_profile = manager.get_active_profile()

        # Get info for each profile
        profile_info = []
        for profile_name in profiles:
            try:
                info = manager.get_profile_info(profile_name)
                profile_info.append({
                    "name": info["name"],
                    "description": info["description"],
                    "is_active": info["is_active"],
                    "created_at": info["created_at"],
                    "files": info["files"],
                    "tracker_stats": info.get("tracker_stats"),
                })
            except Exception as e:
                profile_info.append({
                    "name": profile_name,
                    "error": str(e),
                })

        return format_success_response({
            "profiles": profile_info,
            "count": len(profiles),
            "active_profile": active_profile,
        })


class ProfileCreateTool(BaseTool):
    """Create a new profile"""

    def __init__(self):
        super().__init__("create", "Create a new profile")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        params = self.validate_parameters(
            kwargs,
            required=["name"],
            optional=["description", "clone_from"],
        )

        profile_name = params["name"]
        description = params.get("description")
        clone_from = params.get("clone_from")

        manager = ProfileManager()

        # Create the profile
        manager.create_profile(
            profile_name=profile_name,
            description=description,
            clone_from=clone_from,
        )

        # Get info about created profile
        info = manager.get_profile_info(profile_name)
        paths = ProfilePaths(profile_name)

        return format_success_response(
            data={
                "profile": info,
                "paths": {
                    "templates": str(paths.templates_dir),
                    "data": str(paths.data_dir),
                    "reports": str(paths.reports_dir),
                    "resume": str(paths.resume_path),
                    "requirements": str(paths.requirements_path),
                },
                "next_steps": [
                    f"Edit resume: {paths.resume_path}",
                    f"Edit requirements: {paths.requirements_path}",
                    f"Switch to profile: use profile_management.switch tool",
                ],
            },
            message=f"Profile '{profile_name}' created successfully",
        )


class ProfileSwitchTool(BaseTool):
    """Switch to a different profile"""

    def __init__(self):
        super().__init__("switch", "Switch to a different profile")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        params = self.validate_parameters(kwargs, required=["name"])

        profile_name = params["name"]
        manager = ProfileManager()

        # "current" doesn't make sense for switch
        if profile_name == "current":
            current = manager.get_active_profile()
            raise ProfileNotFoundError(
                profile_name="current",
                available_profiles=manager.list_profiles(),
                suggestion=f"Already on profile '{current}'. Specify a different profile name to switch.",
            )

        # Validate profile exists before switching
        if not manager.profile_exists(profile_name):
            raise ProfileNotFoundError(
                profile_name=profile_name,
                available_profiles=manager.list_profiles(),
            )

        # Switch profile
        manager.switch_profile(profile_name)

        # Get info about new active profile
        info = manager.get_profile_info(profile_name)

        return format_success_response(
            data={"profile": info, "status": "active"},
            message=f"Switched to profile: {profile_name}",
        )


class ProfileDeleteTool(BaseTool):
    """Delete a profile"""

    def __init__(self):
        super().__init__("delete", "Delete a profile")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        params = self.validate_parameters(
            kwargs,
            required=["name"],
            optional=["force"],
        )

        profile_name = params["name"]
        force = params.get("force", False)

        manager = ProfileManager()

        # "current" doesn't make sense for delete - be explicit
        if profile_name == "current":
            current = manager.get_active_profile()
            raise ProfileNotFoundError(
                profile_name="current",
                available_profiles=manager.list_profiles(),
                suggestion=f"To delete the active profile '{current}', use that name explicitly. Deleting requires explicit profile names for safety.",
            )

        # Validate profile exists
        if not manager.profile_exists(profile_name):
            raise ProfileNotFoundError(
                profile_name=profile_name,
                available_profiles=manager.list_profiles(),
            )

        # Get info before deletion
        info = manager.get_profile_info(profile_name)
        is_active = info["is_active"]

        # Delete profile
        manager.delete_profile(profile_name, force=force)

        result = {
            "deleted_profile": profile_name,
        }

        if is_active:
            remaining = manager.list_profiles()
            result["warning"] = "Deleted active profile. Switch to another profile."
            if remaining:
                result["available_profiles"] = remaining

        return format_success_response(
            data=result,
            message=f"Profile '{profile_name}' deleted successfully",
        )


class ProfileInfoTool(BaseTool):
    """Get detailed information about a profile"""

    def __init__(self):
        super().__init__("info", "Get detailed profile information")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        params = self.validate_parameters(
            kwargs,
            required=[],  # No required params
            optional=["name"],  # Name is optional - defaults to current
        )

        manager = ProfileManager()

        # Resolve profile name - use "current" or active profile if not specified
        profile_name = params.get("name")
        if not profile_name or profile_name == "current":
            profile_name = manager.get_active_profile()

        # Validate profile exists
        if not manager.profile_exists(profile_name):
            raise ProfileNotFoundError(
                profile_name=profile_name,
                available_profiles=manager.list_profiles(),
            )

        # Get comprehensive profile info
        info = manager.get_profile_info(profile_name)

        # Get email configuration
        email_config = manager.get_profile_email_config(profile_name)
        if email_config:
            info["email_config"] = email_config

        return format_success_response({"profile": info})


class ProfileStatsTool(BaseTool):
    """Get statistics for all profiles"""

    def __init__(self):
        super().__init__("stats", "Get statistics for all profiles")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        manager = ProfileManager()
        profiles_info = manager.get_all_profiles_info()

        # Calculate aggregate statistics
        total_jobs = sum(
            p.get("tracker_stats", {}).get("total_jobs", 0)
            for p in profiles_info
        )
        total_data_files = sum(
            p["files"]["data_files"]
            for p in profiles_info
        )
        total_reports = sum(
            p["files"]["reports"]
            for p in profiles_info
        )

        return format_success_response({
            "profiles": profiles_info,
            "summary": {
                "total_profiles": len(profiles_info),
                "active_profile": manager.get_active_profile(),
                "total_jobs_tracked": total_jobs,
                "total_data_files": total_data_files,
                "total_reports": total_reports,
            },
        })


# =============================================================================
# Tool Registration
# =============================================================================

# Register all profile tools
profile_registry.register("list", ProfileListTool())
profile_registry.register("create", ProfileCreateTool())
profile_registry.register("switch", ProfileSwitchTool())
profile_registry.register("delete", ProfileDeleteTool())
profile_registry.register("info", ProfileInfoTool())
profile_registry.register("stats", ProfileStatsTool())


# =============================================================================
# Main Execute Function
# =============================================================================


async def execute(tool_action: str, parameters: Dict[str, Any]) -> Any:
    """
    Execute a profile management tool

    Args:
        tool_action: Tool action name (e.g., 'list', 'create')
        parameters: Tool parameters

    Returns:
        Tool execution result

    Raises:
        ValueError: If tool not found
    """
    tool = profile_registry.get(tool_action)

    if not tool:
        available = profile_registry.list_tools()
        raise ValueError(
            f"Unknown profile tool: {tool_action}. "
            f"Available tools: {', '.join(available)}"
        )

    return await tool.execute(**parameters)
