"""
Email Configuration Tools

Tools for managing email setup and sending reports.
"""

import sys
import os
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.profile_manager import ProfileManager
from .base import email_registry, BaseTool
from ..utils.response_formatter import format_success_response


class EmailProfileSetTool(BaseTool):
    """Set profile-specific email configuration"""

    def __init__(self):
        super().__init__("profile_set", "Set email configuration for a profile")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        params = self.validate_parameters(
            kwargs,
            required=["profile_name", "recipients"],
            optional=["subject_prefix", "enabled", "min_matches"],
        )

        profile_name = params["profile_name"]
        recipients = params["recipients"]
        if isinstance(recipients, str):
            recipients = [r.strip() for r in recipients.split(",")]

        manager = ProfileManager()
        manager.set_profile_email_config(
            profile_name=profile_name,
            recipients=recipients,
            subject_prefix=params.get("subject_prefix"),
            enabled=params.get("enabled"),
            min_matches=params.get("min_matches"),
        )

        return format_success_response(
            data={
                "profile": profile_name,
                "email_config": {
                    "recipients": recipients,
                    "subject_prefix": params.get("subject_prefix"),
                    "enabled": params.get("enabled"),
                    "min_matches": params.get("min_matches"),
                },
            },
            message=f"Email configuration updated for profile: {profile_name}",
        )


class EmailProfileShowTool(BaseTool):
    """Show email configuration for a profile"""

    def __init__(self):
        super().__init__("profile_show", "Show email configuration for a profile")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        params = self.validate_parameters(kwargs, required=["profile_name"])

        profile_name = params["profile_name"]
        manager = ProfileManager()

        profile_config = manager.get_profile_email_config(profile_name)

        # Get global config for comparison
        from dotenv import load_dotenv

        load_dotenv()
        global_config = {
            "recipients": os.getenv("EMAIL_RECIPIENT", ""),
            "subject_prefix": os.getenv("EMAIL_SUBJECT_PREFIX", "[Job Matcher]"),
            "enabled": os.getenv("EMAIL_ENABLED", "true").lower() == "true",
            "min_matches": int(os.getenv("EMAIL_MIN_MATCHES", "1")),
        }

        return format_success_response({
            "profile": profile_name,
            "profile_config": profile_config,
            "global_config": global_config,
            "using_profile_config": profile_config is not None,
        })


# Register tools
email_registry.register("profile_set", EmailProfileSetTool())
email_registry.register("profile_show", EmailProfileShowTool())


async def execute(tool_action: str, parameters: Dict[str, Any]) -> Any:
    """Execute an email tool"""
    tool = email_registry.get(tool_action)
    if not tool:
        raise ValueError(f"Unknown email tool: {tool_action}")
    return await tool.execute(**parameters)
