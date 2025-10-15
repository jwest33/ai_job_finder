"""
MCP Server Configuration

Configuration settings for the MCP server including authentication,
rate limiting, and capability definitions.
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class MCPServerConfig:
    """MCP Server configuration"""

    # Server settings
    HOST: str = os.getenv("MCP_SERVER_HOST", "localhost")
    PORT: int = int(os.getenv("MCP_SERVER_PORT", "3000"))
    LOG_LEVEL: str = os.getenv("MCP_LOG_LEVEL", "INFO")

    # Authentication
    AUTH_ENABLED: bool = os.getenv("MCP_AUTH_ENABLED", "true").lower() == "true"
    AUTH_TOKEN: Optional[str] = os.getenv("MCP_AUTH_TOKEN")

    # Server metadata
    NAME: str = "job-search-mcp-server"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "MCP server for AI-powered job search system"

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_CALLS: int = 100  # calls per window
    RATE_LIMIT_WINDOW: int = 60  # seconds

    # Feature flags
    ALLOW_DESTRUCTIVE_OPERATIONS: bool = True
    REQUIRE_CONFIRMATION: bool = True
    ENABLE_AUDIT_LOG: bool = True

    # Sensitive keys to filter from responses
    SENSITIVE_KEYS = {
        "password",
        "token",
        "secret",
        "api_key",
        "credential",
        "auth",
        "iproyal_password",
        "iproyal_username",
    }

    @classmethod
    def is_sensitive_key(cls, key: str) -> bool:
        """Check if a key contains sensitive data"""
        key_lower = key.lower()
        return any(sensitive in key_lower for sensitive in cls.SENSITIVE_KEYS)


# Tool capabilities configuration
TOOL_CAPABILITIES = {
    "profile_management": {
        "list": {"destructive": False, "requires_auth": False},
        "create": {"destructive": False, "requires_auth": True},
        "switch": {"destructive": False, "requires_auth": True},
        "delete": {"destructive": True, "requires_auth": True},
        "info": {"destructive": False, "requires_auth": False},
    },
    "scraper": {
        "search": {"destructive": False, "requires_auth": True},
        "config_show": {"destructive": False, "requires_auth": False},
        "config_update": {"destructive": False, "requires_auth": True},
        "test_proxy": {"destructive": False, "requires_auth": True},
    },
    "matcher": {
        "full_pipeline": {"destructive": False, "requires_auth": True},
        "score": {"destructive": False, "requires_auth": True},
        "retry_failed": {"destructive": False, "requires_auth": True},
    },
    "tracker": {
        "stats": {"destructive": False, "requires_auth": False},
        "failures": {"destructive": False, "requires_auth": False},
    },
    "templates": {
        "list": {"destructive": False, "requires_auth": False},
        "validate": {"destructive": False, "requires_auth": False},
    },
    "email": {
        "profile_set": {"destructive": False, "requires_auth": True},
        "profile_show": {"destructive": False, "requires_auth": False},
    },
    "system": {
        "doctor": {"destructive": False, "requires_auth": False},
        "env_get": {"destructive": False, "requires_auth": False},
        "env_set": {"destructive": False, "requires_auth": True},
        "full_pipeline": {"destructive": False, "requires_auth": True},
    },
}
