"""
Error Handling Utilities

Centralized error handling for MCP server operations.
"""

import traceback
from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class MCPError(Exception):
    """Base exception for MCP server errors"""

    def __init__(
        self,
        message: str,
        error_type: str = "MCPError",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(MCPError):
    """Validation error"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_type="ValidationError",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class NotFoundError(MCPError):
    """Resource not found error"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_type="NotFoundError",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class AuthenticationError(MCPError):
    """Authentication error"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_type="AuthenticationError",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class PermissionError(MCPError):
    """Permission denied error"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_type="PermissionError",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ToolExecutionError(MCPError):
    """Tool execution error"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_type="ToolExecutionError",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class ProfileNotFoundError(NotFoundError):
    """Profile not found error - provides helpful context"""

    def __init__(
        self,
        profile_name: str,
        available_profiles: Optional[list] = None,
        suggestion: Optional[str] = None,
    ):
        available_profiles = available_profiles or []

        # Build helpful error message
        message = f"Profile '{profile_name}' does not exist"

        # Add suggestion
        if not suggestion:
            if profile_name == "current":
                suggestion = "Use profile_management.list to see available profiles and get the active profile"
            elif available_profiles:
                suggestion = f"Available profiles: {', '.join(available_profiles)}"
            else:
                suggestion = "Use profile_management.create to create a new profile"

        details = {
            "requested_profile": profile_name,
            "available_profiles": available_profiles,
            "suggestion": suggestion,
            "helpful_tools": ["profile_management.list", "profile_management.create"],
        }

        super().__init__(message=message, details=details)


class ResourceNotFoundError(NotFoundError):
    """Resource not found error - provides helpful context"""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        suggestion: Optional[str] = None,
    ):
        message = f"{resource_type.title()} '{resource_id}' not found"

        details = {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "suggestion": suggestion or f"Check that the {resource_type} exists and you have access to it",
        }

        super().__init__(message=message, details=details)


def handle_exception(e: Exception, tool_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Convert exception to error response

    Args:
        e: Exception to handle
        tool_name: Name of tool that raised the exception

    Returns:
        Error response dict with LLM-friendly suggestions
    """
    if isinstance(e, MCPError):
        response = {
            "success": False,
            "error": e.message,
            "error_type": e.error_type,
            "details": e.details,
        }

        # Extract suggestion if present in details
        if "suggestion" in e.details:
            response["suggestion"] = e.details["suggestion"]

        # Extract helpful tools if present
        if "helpful_tools" in e.details:
            response["helpful_tools"] = e.details["helpful_tools"]

        return response

    elif isinstance(e, HTTPException):
        return {
            "success": False,
            "error": e.detail,
            "error_type": "HTTPException",
            "details": {"status_code": e.status_code},
        }

    else:
        # Unexpected error
        error_details = {
            "exception_type": type(e).__name__,
            "exception_message": str(e),
        }

        if tool_name:
            error_details["tool"] = tool_name

        return {
            "success": False,
            "error": "An unexpected error occurred",
            "error_type": "UnexpectedError",
            "details": error_details,
        }


def safe_execute(func, *args, tool_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Safely execute a function and handle any exceptions

    Args:
        func: Function to execute
        *args: Positional arguments
        tool_name: Name of tool (for error context)
        **kwargs: Keyword arguments

    Returns:
        Result dict with success/error status
    """
    try:
        result = func(*args, **kwargs)
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        return handle_exception(e, tool_name=tool_name)
