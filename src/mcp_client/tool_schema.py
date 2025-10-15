"""
Tool Schema Generator

Fetches and formats MCP tool schemas for LLM consumption.
"""

import requests
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class ToolSchemaGenerator:
    """Generator for MCP tool schemas"""

    def __init__(self, mcp_url: str = "http://localhost:3000", auth_token: str = None):
        """
        Initialize schema generator

        Args:
            mcp_url: MCP server URL
            auth_token: Optional authentication token
        """
        self.mcp_url = mcp_url.rstrip("/")
        self.auth_token = auth_token
        self._cached_schemas = None

    def get_tool_schemas(self, refresh: bool = False) -> Dict[str, Any]:
        """
        Get all tool schemas from MCP server

        Args:
            refresh: Force refresh from server

        Returns:
            Dict of tool schemas keyed by tool name
        """
        if self._cached_schemas and not refresh:
            return self._cached_schemas

        try:
            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"

            response = requests.get(f"{self.mcp_url}/tools", headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            if not data.get("success"):
                raise ValueError("Failed to fetch tools from MCP server")

            tools = data.get("data", {}).get("tools", [])

            # Build schemas
            schemas = {}
            for tool in tools:
                tool_name = tool["name"]
                schemas[tool_name] = {
                    "name": tool_name,
                    "category": tool["category"],
                    "destructive": tool["destructive"],
                    "requires_auth": tool["requires_auth"],
                    "accessible": tool["accessible"],
                    "parameters": self._infer_parameters(tool_name),
                }

            self._cached_schemas = schemas
            return schemas

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch tool schemas: {e}")
            return {}

    def _infer_parameters(self, tool_name: str) -> Dict[str, Any]:
        """
        Infer parameters for a tool based on its name

        Args:
            tool_name: Full tool name (category.action)

        Returns:
            Dict of parameter schemas
        """
        # Hardcoded schemas for known tools
        # In a real implementation, these would be fetched from the server
        schemas = {
            # Profile Management
            "profile_management.list": {},
            "profile_management.create": {
                "name": {"type": "string", "required": True, "description": "Profile name"},
                "description": {"type": "string", "required": False, "description": "Profile description"},
                "clone_from": {"type": "string", "required": False, "description": "Profile to clone from"},
            },
            "profile_management.switch": {
                "name": {"type": "string", "required": True, "description": "Profile name to switch to"},
            },
            "profile_management.delete": {
                "name": {"type": "string", "required": True, "description": "Profile name to delete"},
                "force": {"type": "boolean", "required": False, "description": "Skip safety checks"},
            },
            "profile_management.info": {
                "name": {"type": "string", "required": True, "description": "Profile name"},
            },
            "profile_management.stats": {},

            # Scraper
            "scraper.search": {
                "jobs": {"type": "array", "required": False, "description": "Job titles to search"},
                "locations": {"type": "array", "required": False, "description": "Locations to search"},
                "results": {"type": "integer", "required": False, "description": "Results per search"},
                "scraper": {"type": "string", "required": False, "description": "Scraper to use (indeed, glassdoor, all)"},
                "dry_run": {"type": "boolean", "required": False, "description": "Preview without executing"},
            },
            "scraper.config_show": {},
            "scraper.config_update": {
                "results_per_search": {"type": "integer", "required": False},
                "proxy_rotation_count": {"type": "integer", "required": False},
                "output_format": {"type": "string", "required": False},
                "deduplicate": {"type": "boolean", "required": False},
                "rate_limit_delay": {"type": "number", "required": False},
            },
            "scraper.test_proxy": {},

            # Matcher
            "matcher.full_pipeline": {
                "input_file": {"type": "string", "required": False, "description": "Input jobs file"},
                "source": {"type": "string", "required": False, "description": "Filter by source"},
                "min_score": {"type": "integer", "required": False, "description": "Minimum match score"},
                "resume_checkpoint": {"type": "boolean", "required": False, "description": "Resume from checkpoint"},
                "send_email": {"type": "boolean", "required": False, "description": "Send email notification (default: true)"},
            },
            "matcher.score": {
                "input_file": {"type": "string", "required": False},
                "min_score": {"type": "integer", "required": False},
            },
            "matcher.retry_failed": {
                "stage": {"type": "string", "required": True, "description": "Stage to retry (scoring, analysis, optimization)"},
                "retry_temp": {"type": "number", "required": False, "description": "Override temperature"},
                "retry_tokens": {"type": "integer", "required": False, "description": "Override max tokens"},
            },

            # Tracker
            "tracker.stats": {},
            "tracker.failures": {},

            # Templates
            "template.list": {},
            "template.validate": {},

            # Email
            "email.profile_set": {
                "profile_name": {"type": "string", "required": True},
                "recipients": {"type": "string", "required": True, "description": "Comma-separated emails"},
                "subject_prefix": {"type": "string", "required": False},
                "enabled": {"type": "boolean", "required": False},
                "min_matches": {"type": "integer", "required": False},
            },
            "email.profile_show": {
                "profile_name": {"type": "string", "required": True},
            },

            # System
            "system.doctor": {},
            "system.env_get": {
                "key": {"type": "string", "required": True, "description": "Environment variable name"},
            },
            "system.env_set": {
                "key": {"type": "string", "required": True},
                "value": {"type": "string", "required": True},
            },
            "system.full_pipeline": {
                "jobs": {"type": "array", "required": False, "description": "Job titles to search"},
                "locations": {"type": "array", "required": False, "description": "Locations to search"},
                "results": {"type": "integer", "required": False, "description": "Results per search"},
                "min_score": {"type": "integer", "required": False, "description": "Minimum match score"},
                "scrapers": {"type": "array", "required": False, "description": "Scrapers to use (default: ['indeed', 'glassdoor'])"},
            },
        }

        return schemas.get(tool_name, {})

    def format_for_llm(self, schemas: Dict[str, Any] = None) -> str:
        """
        Format tool schemas for LLM system prompt

        Args:
            schemas: Tool schemas (will fetch if not provided)

        Returns:
            Formatted string for system prompt
        """
        if schemas is None:
            schemas = self.get_tool_schemas()

        if not schemas:
            return "No tools available."

        # Group by category
        by_category = {}
        for tool_name, schema in schemas.items():
            category = schema["category"]
            if category not in by_category:
                by_category[category] = []
            by_category[category].append((tool_name, schema))

        # Format output
        lines = []
        for category in sorted(by_category.keys()):
            lines.append(f"\n## {category.replace('_', ' ').title()}")

            for tool_name, schema in sorted(by_category[category]):
                lines.append(f"\n### {tool_name}")

                # Add warning for destructive tools
                if schema["destructive"]:
                    lines.append(" **DESTRUCTIVE OPERATION** - Use with caution")

                # Add parameters
                params = schema.get("parameters", {})
                if params:
                    lines.append("**Parameters:**")
                    for param_name, param_schema in params.items():
                        required = " (required)" if param_schema.get("required") else " (optional)"
                        param_type = param_schema.get("type", "any")
                        description = param_schema.get("description", "")
                        lines.append(f"- `{param_name}` ({param_type}){required}: {description}")
                else:
                    lines.append("**Parameters:** None")

        return "\n".join(lines)

    def get_tool_names(self) -> List[str]:
        """
        Get list of all tool names

        Returns:
            List of tool names
        """
        schemas = self.get_tool_schemas()
        return list(schemas.keys())

    def get_tool_by_category(self, category: str) -> List[str]:
        """
        Get tools by category

        Args:
            category: Category name

        Returns:
            List of tool names in category
        """
        schemas = self.get_tool_schemas()
        return [
            name for name, schema in schemas.items()
            if schema["category"] == category
        ]
