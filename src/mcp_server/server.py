"""
MCP Server - Main FastAPI Application

FastAPI-based MCP server that exposes job search system functionality
through RESTful endpoints following the Model Context Protocol.
"""

import logging
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pathlib import Path

from .config import MCPServerConfig, TOOL_CAPABILITIES
from .api.router import api_router
from .auth import require_auth, optional_auth, MCPAuth
from .utils.response_formatter import (
    format_success_response,
    format_error_response,
    format_tool_metadata,
)
from .utils.error_handler import (
    handle_exception,
    safe_execute,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    PermissionError as MCPPermissionError,
    MCPError,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, MCPServerConfig.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models
# =============================================================================


class ServerInfo(BaseModel):
    """Server information"""

    name: str
    version: str
    description: str
    capabilities: Dict[str, Any]


class ToolRequest(BaseModel):
    """Generic tool execution request"""

    tool: str = Field(..., description="Name of the tool to execute")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Tool parameters"
    )


class ToolResponse(BaseModel):
    """Generic tool execution response"""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ResourceRequest(BaseModel):
    """Resource retrieval request"""

    uri: str = Field(..., description="Resource URI (e.g., 'profile://default/config')")


class ResourceResponse(BaseModel):
    """Resource retrieval response"""

    success: bool
    uri: str
    data: Optional[Any] = None
    content_type: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Lifespan Management
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    # Startup
    logger.info(f"Starting MCP Server v{MCPServerConfig.VERSION}")
    logger.info(f"Server: {MCPServerConfig.HOST}:{MCPServerConfig.PORT}")
    logger.info(f"Authentication: {'Enabled' if MCPServerConfig.AUTH_ENABLED else 'Disabled'}")

    if MCPServerConfig.AUTH_ENABLED and not MCPServerConfig.AUTH_TOKEN:
        logger.warning("Auth is enabled but no token configured!")
        logger.warning("Generate one with: python -c \"from mcp_server.auth import MCPAuth; print(MCPAuth.generate_token())\"")

    yield

    # Shutdown
    logger.info("Shutting down MCP Server")


# =============================================================================
# FastAPI App Initialization
# =============================================================================

app = FastAPI(
    title=MCPServerConfig.NAME,
    description=MCPServerConfig.DESCRIPTION,
    version=MCPServerConfig.VERSION,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API router for web application
app.include_router(api_router)

# Serve static files from web build (if exists)
web_dist = Path(__file__).parent.parent.parent / "web" / "dist"
if web_dist.exists():
    app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="static")


# =============================================================================
# Root Endpoints
# =============================================================================


@app.get("/", response_model=ServerInfo)
async def root():
    """Get server information and capabilities"""
    return ServerInfo(
        name=MCPServerConfig.NAME,
        version=MCPServerConfig.VERSION,
        description=MCPServerConfig.DESCRIPTION,
        capabilities={
            "tools": list(TOOL_CAPABILITIES.keys()),
            "authentication": MCPServerConfig.AUTH_ENABLED,
            "rate_limiting": MCPServerConfig.RATE_LIMIT_ENABLED,
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": MCPServerConfig.VERSION}


@app.get("/auth/generate-token")
async def generate_auth_token():
    """Generate a new authentication token"""
    token = MCPAuth.generate_token()
    return {
        "token": token,
        "message": "Save this token in your .env file as MCP_AUTH_TOKEN",
        "note": "This token will not be shown again",
    }


# =============================================================================
# Tool Endpoints
# =============================================================================


@app.get("/tools")
async def list_tools(current_user: dict = Depends(optional_auth)):
    """List all available tools"""
    tools = []

    for category, category_tools in TOOL_CAPABILITIES.items():
        for tool_name, config in category_tools.items():
            full_name = f"{category}.{tool_name}"
            tools.append(
                {
                    "name": full_name,
                    "category": category,
                    "destructive": config["destructive"],
                    "requires_auth": config["requires_auth"],
                    "accessible": (
                        not config["requires_auth"]
                        or current_user.get("authenticated", False)
                    ),
                }
            )

    return format_success_response({"tools": tools, "count": len(tools)})


@app.post("/tools/execute", response_model=ToolResponse)
async def execute_tool(
    request: ToolRequest,
    current_user: dict = Depends(require_auth),
):
    """
    Execute a tool

    This is the main endpoint for tool execution. Tools are dispatched
    to their respective handlers based on the tool name.
    """
    tool_name = request.tool
    parameters = request.parameters

    logger.info(f"Executing tool: {tool_name} with parameters: {parameters}")

    try:
        # Parse tool name (category.tool_name)
        if "." not in tool_name:
            raise ValidationError(
                f"Invalid tool name format: {tool_name}. Expected format: 'category.tool_name'"
            )

        category, tool_action = tool_name.split(".", 1)

        # Check if tool exists
        if category not in TOOL_CAPABILITIES:
            raise ValidationError(f"Unknown tool category: {category}")

        if tool_action not in TOOL_CAPABILITIES[category]:
            raise ValidationError(f"Unknown tool: {tool_name}")

        # Check authentication requirement
        tool_config = TOOL_CAPABILITIES[category][tool_action]
        if tool_config["requires_auth"] and not current_user.get("authenticated", False):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Tool {tool_name} requires authentication",
            )

        # Import and execute tool handler
        # Tool handlers will be implemented in separate modules
        result = await dispatch_tool(category, tool_action, parameters)

        # Add metadata
        metadata = format_tool_metadata(
            tool_name=tool_name,
            destructive=tool_config["destructive"],
            requires_auth=tool_config["requires_auth"],
        )

        return ToolResponse(
            success=True,
            data=result,
            metadata=metadata,
        )

    except Exception as e:
        # Log based on error type - reduce noise for known user errors
        if isinstance(e, (ValidationError, NotFoundError)):
            # User errors - log at INFO level without stack trace
            logger.info(f"Tool '{tool_name}' - User error: {e}")
        elif isinstance(e, (AuthenticationError, MCPPermissionError)):
            # Auth errors - log at WARNING level without stack trace
            logger.warning(f"Tool '{tool_name}' - Auth error: {e}")
        elif isinstance(e, MCPError):
            # Other MCP errors - log at ERROR level without stack trace
            logger.error(f"Tool '{tool_name}' - MCP error: {e}")
        else:
            # Unexpected errors - log at ERROR level WITH stack trace
            logger.error(f"Tool '{tool_name}' - Unexpected error: {e}", exc_info=True)

        error_response = handle_exception(e, tool_name=tool_name)

        return ToolResponse(
            success=error_response["success"],
            error=error_response.get("error"),
            error_type=error_response.get("error_type"),
            metadata=error_response.get("details"),
        )


async def dispatch_tool(category: str, tool_action: str, parameters: Dict[str, Any]) -> Any:
    """
    Dispatch tool execution to appropriate handler

    Args:
        category: Tool category (e.g., 'profile', 'scraper')
        tool_action: Tool action (e.g., 'list', 'create')
        parameters: Tool parameters

    Returns:
        Tool execution result

    Raises:
        NotImplementedError: If tool handler not implemented yet
    """
    # Import tool modules dynamically
    # This allows us to implement tools incrementally

    if category == "profile_management":
        from .tools import profile_tools

        return await profile_tools.execute(tool_action, parameters)

    elif category == "scraper":
        from .tools import scraper_tools

        return await scraper_tools.execute(tool_action, parameters)

    elif category == "matcher":
        from .tools import matcher_tools

        return await matcher_tools.execute(tool_action, parameters)

    elif category == "tracker":
        from .tools import tracker_tools

        return await tracker_tools.execute(tool_action, parameters)

    elif category == "templates":
        from .tools import template_tools

        return await template_tools.execute(tool_action, parameters)

    elif category == "email":
        from .tools import email_tools

        return await email_tools.execute(tool_action, parameters)

    elif category == "system":
        from .tools import system_tools

        return await system_tools.execute(tool_action, parameters)

    else:
        raise NotImplementedError(f"Tool category '{category}' not yet implemented")


# =============================================================================
# Resource Endpoints
# =============================================================================


@app.post("/resources/get", response_model=ResourceResponse)
async def get_resource(
    request: ResourceRequest,
    current_user: dict = Depends(optional_auth),
):
    """
    Retrieve a resource by URI

    Resources follow URI format: protocol://path/to/resource
    Examples:
      - profile://default/config
      - jobs://scraped/indeed/latest
      - config://env
    """
    uri = request.uri

    logger.info(f"Retrieving resource: {uri}")

    try:
        # Parse URI
        if "://" not in uri:
            raise ValidationError(f"Invalid resource URI: {uri}")

        protocol, path = uri.split("://", 1)

        # Dispatch to resource provider
        result = await dispatch_resource(protocol, path, current_user)

        return ResourceResponse(
            success=True,
            uri=uri,
            data=result["data"],
            content_type=result.get("content_type", "application/json"),
        )

    except Exception as e:
        # Log based on error type - reduce noise for known user errors
        if isinstance(e, (ValidationError, NotFoundError)):
            logger.info(f"Resource '{uri}' - User error: {e}")
        elif isinstance(e, (AuthenticationError, MCPPermissionError)):
            logger.warning(f"Resource '{uri}' - Auth error: {e}")
        elif isinstance(e, MCPError):
            logger.error(f"Resource '{uri}' - MCP error: {e}")
        else:
            logger.error(f"Resource '{uri}' - Unexpected error: {e}", exc_info=True)

        error_response = handle_exception(e)

        return ResourceResponse(
            success=False,
            uri=uri,
            error=error_response.get("error"),
        )


async def dispatch_resource(
    protocol: str, path: str, current_user: dict
) -> Dict[str, Any]:
    """
    Dispatch resource retrieval to appropriate provider

    Args:
        protocol: Resource protocol (e.g., 'profile', 'jobs', 'config')
        path: Resource path
        current_user: Current user context

    Returns:
        Resource data

    Raises:
        NotImplementedError: If resource provider not implemented yet
    """
    if protocol == "profile":
        from .resources import profile_resources

        return await profile_resources.get(path, current_user)

    elif protocol == "jobs":
        from .resources import job_resources

        return await job_resources.get(path, current_user)

    elif protocol == "config":
        from .resources import config_resources

        return await config_resources.get(path, current_user)

    else:
        raise NotImplementedError(f"Resource protocol '{protocol}' not yet implemented")


# =============================================================================
# Main Entry Point
# =============================================================================


def start_server():
    """Start the MCP server"""
    import uvicorn

    uvicorn.run(
        app,
        host=MCPServerConfig.HOST,
        port=MCPServerConfig.PORT,
        log_level=MCPServerConfig.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    start_server()
