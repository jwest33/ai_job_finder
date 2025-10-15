"""
Base Tool Framework

Base classes and utilities for implementing MCP tools.
"""

from typing import Any, Dict, Callable, Optional
from abc import ABC, abstractmethod


class BaseTool(ABC):
    """Base class for MCP tools"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """
        Execute the tool

        Args:
            **kwargs: Tool parameters

        Returns:
            Tool execution result
        """
        pass

    def validate_parameters(self, parameters: Dict[str, Any], required: list, optional: list = None) -> Dict[str, Any]:
        """
        Validate tool parameters

        Args:
            parameters: Input parameters
            required: Required parameter names
            optional: Optional parameter names (default: empty list)

        Returns:
            Validated parameters

        Raises:
            ValueError: If required parameters are missing or unknown parameters provided
        """
        optional = optional or []
        all_params = set(required + optional)

        # Check for missing required parameters
        missing = [p for p in required if p not in parameters]
        if missing:
            raise ValueError(f"Missing required parameters: {', '.join(missing)}")

        # Check for unknown parameters
        unknown = [p for p in parameters if p not in all_params]
        if unknown:
            raise ValueError(f"Unknown parameters: {', '.join(unknown)}")

        return parameters


class ToolRegistry:
    """Registry for tool handlers"""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}

    def register(self, name: str, handler: Callable):
        """Register a tool handler"""
        self._tools[name] = handler

    def get(self, name: str) -> Optional[Callable]:
        """Get a tool handler"""
        return self._tools.get(name)

    def list_tools(self) -> list:
        """List all registered tools"""
        return list(self._tools.keys())


# Create singleton registry instances for each tool category
profile_registry = ToolRegistry()
scraper_registry = ToolRegistry()
matcher_registry = ToolRegistry()
tracker_registry = ToolRegistry()
template_registry = ToolRegistry()
email_registry = ToolRegistry()
system_registry = ToolRegistry()
