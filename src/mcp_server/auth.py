"""
Authentication and Authorization

Token-based authentication for MCP server operations.
"""

import secrets
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import MCPServerConfig

security = HTTPBearer(auto_error=False)


class MCPAuth:
    """Authentication handler for MCP server"""

    @staticmethod
    def generate_token() -> str:
        """Generate a secure random token"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def verify_token(token: str) -> bool:
        """Verify authentication token"""
        if not MCPServerConfig.AUTH_ENABLED:
            return True

        expected_token = MCPServerConfig.AUTH_TOKEN
        if not expected_token:
            # If no token configured, deny access when auth is enabled
            return False

        return secrets.compare_digest(token, expected_token)

    @staticmethod
    async def get_current_user(
        credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    ) -> dict:
        """
        Dependency for authenticating requests

        Returns:
            User info dict (for now just {"authenticated": True})

        Raises:
            HTTPException: If authentication fails
        """
        if not MCPServerConfig.AUTH_ENABLED:
            return {"authenticated": True, "auth_required": False}

        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not MCPAuth.verify_token(credentials.credentials):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {"authenticated": True, "auth_required": True}


async def require_auth(
    current_user: dict = Security(MCPAuth.get_current_user),
) -> dict:
    """Dependency that requires authentication"""
    return current_user


async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> dict:
    """Dependency that allows optional authentication"""
    if not MCPServerConfig.AUTH_ENABLED:
        return {"authenticated": True, "auth_required": False}

    if credentials is None:
        return {"authenticated": False, "auth_required": True}

    if MCPAuth.verify_token(credentials.credentials):
        return {"authenticated": True, "auth_required": True}

    return {"authenticated": False, "auth_required": True}
