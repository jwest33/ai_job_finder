"""
Configuration Resources

Provides read-only access to system configuration.

URI Format: config://{config_type}

Examples:
  - config://env
  - config://active-profile
  - config://scraper
  - config://matcher
"""

import sys
import os
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.profile_manager import ProfileManager
from src.cli.scraper import get_scraper_config
from ..config import MCPServerConfig


async def get(path: str, current_user: dict) -> Dict[str, Any]:
    """
    Get configuration resource

    Args:
        path: Resource path (e.g., "env", "active-profile")
        current_user: Current user context

    Returns:
        Configuration data
    """
    if path == "env":
        return await _get_env_vars()
    elif path == "active-profile":
        return await _get_active_profile()
    elif path == "scraper":
        return await _get_scraper_config()
    elif path == "matcher":
        return await _get_matcher_config()
    else:
        raise ValueError(f"Unknown config resource: {path}")


async def _get_env_vars() -> Dict[str, Any]:
    """Get environment variables (filtered)"""
    from dotenv import dotenv_values

    env_vars = dotenv_values(".env")

    # Filter sensitive variables
    filtered_vars = {}
    for key, value in env_vars.items():
        if MCPServerConfig.is_sensitive_key(key):
            filtered_vars[key] = "***FILTERED***"
        else:
            filtered_vars[key] = value

    return {
        "data": {
            "env_file": ".env",
            "variables": filtered_vars,
            "count": len(filtered_vars),
        },
        "content_type": "application/json",
    }


async def _get_active_profile() -> Dict[str, Any]:
    """Get active profile information"""
    manager = ProfileManager()
    profile_name = manager.get_active_profile()
    info = manager.get_profile_info(profile_name)

    return {
        "data": {
            "active_profile": profile_name,
            "profile_info": info,
        },
        "content_type": "application/json",
    }


async def _get_scraper_config() -> Dict[str, Any]:
    """Get scraper configuration"""
    config = get_scraper_config()

    # Filter sensitive data
    if MCPServerConfig.is_sensitive_key("iproyal_password"):
        config["iproyal_password"] = "***FILTERED***"
    if MCPServerConfig.is_sensitive_key("iproyal_username"):
        config["iproyal_username"] = "***FILTERED***"

    return {
        "data": {
            "configuration": config,
        },
        "content_type": "application/json",
    }


async def _get_matcher_config() -> Dict[str, Any]:
    """Get matcher configuration"""
    config = {
        "llama_server_url": os.getenv("LLAMA_SERVER_URL", "http://localhost:8080"),
        "llama_context_size": int(os.getenv("LLAMA_CONTEXT_SIZE", "8192")),
        "llama_temperature": float(os.getenv("LLAMA_TEMPERATURE", "0.3")),
        "llama_max_tokens": int(os.getenv("LLAMA_MAX_TOKENS", "2048")),
        "min_match_score": int(os.getenv("MIN_MATCH_SCORE", "70")),
        "match_threads": int(os.getenv("MATCH_THREADS", "4")),
    }

    return {
        "data": {
            "configuration": config,
        },
        "content_type": "application/json",
    }
