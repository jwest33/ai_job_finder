"""
Response Formatting Utilities

Helpers for formatting tool responses and filtering sensitive data.
"""

from typing import Any, Dict, List, Optional
from ..config import MCPServerConfig


def filter_sensitive_data(data: Any, depth: int = 0, max_depth: int = 10) -> Any:
    """
    Recursively filter sensitive data from response

    Args:
        data: Data to filter
        depth: Current recursion depth
        max_depth: Maximum recursion depth

    Returns:
        Filtered data with sensitive values masked
    """
    if depth > max_depth:
        return data

    if isinstance(data, dict):
        filtered = {}
        for key, value in data.items():
            if MCPServerConfig.is_sensitive_key(key):
                filtered[key] = "***FILTERED***"
            else:
                filtered[key] = filter_sensitive_data(value, depth + 1, max_depth)
        return filtered

    elif isinstance(data, list):
        return [filter_sensitive_data(item, depth + 1, max_depth) for item in data]

    else:
        return data


def format_success_response(
    data: Any,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Format successful tool response

    Args:
        data: Response data
        message: Optional success message
        metadata: Optional metadata about the operation

    Returns:
        Formatted success response
    """
    response = {
        "success": True,
        "data": filter_sensitive_data(data),
    }

    if message:
        response["message"] = message

    if metadata:
        response["metadata"] = metadata

    return response


def format_error_response(
    error: str,
    error_type: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Format error response

    Args:
        error: Error message
        error_type: Type of error (e.g., "ValidationError", "NotFoundError")
        details: Optional error details

    Returns:
        Formatted error response
    """
    response = {
        "success": False,
        "error": error,
    }

    if error_type:
        response["error_type"] = error_type

    if details:
        response["details"] = filter_sensitive_data(details)

    return response


def format_list_response(
    items: List[Any],
    total: Optional[int] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Format paginated list response

    Args:
        items: List of items
        total: Total number of items (if known)
        page: Current page number
        page_size: Items per page

    Returns:
        Formatted list response
    """
    response = {
        "success": True,
        "data": {
            "items": [filter_sensitive_data(item) for item in items],
            "count": len(items),
        },
    }

    if total is not None:
        response["data"]["total"] = total

    if page is not None and page_size is not None:
        response["data"]["pagination"] = {
            "page": page,
            "page_size": page_size,
            "has_next": (page * page_size) < (total or len(items)),
        }

    return response


def format_tool_metadata(
    tool_name: str,
    destructive: bool = False,
    requires_auth: bool = True,
    estimated_time: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Format tool metadata for LLM context

    Args:
        tool_name: Name of the tool
        destructive: Whether operation is destructive
        requires_auth: Whether authentication is required
        estimated_time: Estimated execution time

    Returns:
        Tool metadata dict
    """
    metadata = {
        "tool": tool_name,
        "destructive": destructive,
        "requires_auth": requires_auth,
    }

    if estimated_time:
        metadata["estimated_time"] = estimated_time

    if destructive:
        metadata["warning"] = "This operation modifies or deletes data"

    return metadata
