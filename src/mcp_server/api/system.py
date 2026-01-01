"""
System API Endpoints

REST endpoints for system health and profile management.
"""

from typing import List, Optional
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from src.utils.profile_manager import ProfileManager, ProfilePaths

router = APIRouter()


def get_profile_manager() -> ProfileManager:
    """Get ProfileManager with refreshed environment."""
    load_dotenv(override=True)
    return ProfileManager()


class HealthStatus(BaseModel):
    """Health status response"""
    status: str  # healthy, degraded, unhealthy
    version: str
    components: dict


class Profile(BaseModel):
    """Profile info"""
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: Optional[str] = None


@router.get("/health", response_model=HealthStatus)
async def get_health():
    """Get system health status."""
    from src.mcp_server.config import MCPServerConfig

    components = {
        "database": False,
        "llama_server": False,
    }

    # Check database
    try:
        load_dotenv(override=True)
        from src.core.database import get_database
        db = get_database()
        db.fetchone("SELECT 1")
        components["database"] = True
    except Exception:
        pass

    # Check llama server
    try:
        import httpx
        llama_url = os.getenv("LLAMA_SERVER_URL", "http://localhost:8080")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{llama_url}/health")
            components["llama_server"] = response.status_code == 200
    except Exception:
        pass

    # Determine overall status
    if all(components.values()):
        status = "healthy"
    elif any(components.values()):
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthStatus(
        status=status,
        version=MCPServerConfig.VERSION,
        components=components,
    )


@router.get("/profiles", response_model=List[Profile])
async def get_profiles():
    """Get all available profiles."""
    manager = get_profile_manager()
    profiles = manager.list_profiles()

    active_profile = manager.get_active_profile()

    result = []
    for name in profiles:
        info = manager.get_profile_info(name)
        result.append(Profile(
            name=name,
            description=info.get("description") if info else None,
            is_active=name == active_profile,
            created_at=info.get("created_at") if info else None,
        ))

    return result


@router.post("/profiles/{profile_name}/activate")
async def activate_profile(profile_name: str):
    """Switch to a different profile."""
    manager = get_profile_manager()

    if not manager.profile_exists(profile_name):
        raise HTTPException(status_code=404, detail=f"Profile '{profile_name}' not found")

    success = manager.switch_profile(profile_name)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to switch profile")

    # Verify the switch by getting fresh profile info
    load_dotenv(override=True)
    active = os.getenv("ACTIVE_PROFILE", "default")

    # Also clear database cache again to be safe
    try:
        from src.core.database import DatabaseManager
        DatabaseManager.close_all()
    except ImportError:
        pass

    return {
        "success": True,
        "message": f"Switched to profile '{profile_name}'",
        "active_profile": active
    }


@router.get("/debug/profile-state")
async def get_profile_debug_state():
    """Debug endpoint to check current profile state."""
    from src.core.database import DatabaseManager
    from src.utils.profile_manager import ProfilePaths, get_active_profile

    active_profile = get_active_profile()  # Read directly from .env file
    paths = ProfilePaths()

    # Get database info
    db_instances = list(DatabaseManager._instances.keys())

    # Get job count from current profile
    job_count = None
    db_path = None
    try:
        from src.core.database import get_database
        db = get_database()
        db_path = str(db.db_path)
        result = db.fetchone("SELECT COUNT(*) FROM jobs")
        job_count = result[0] if result else 0
    except Exception as e:
        job_count = f"Error: {e}"

    return {
        "active_profile": active_profile,
        "profile_paths": {
            "base_dir": str(paths.base_dir),
            "templates_dir": str(paths.templates_dir),
            "data_dir": str(paths.data_dir),
        },
        "database": {
            "path": db_path,
            "cached_instances": db_instances,
            "job_count": job_count,
        }
    }


@router.get("/profiles/{profile_name}")
async def get_profile_info(profile_name: str):
    """Get detailed profile information."""
    manager = get_profile_manager()

    if not manager.profile_exists(profile_name):
        raise HTTPException(status_code=404, detail=f"Profile '{profile_name}' not found")

    info = manager.get_profile_info(profile_name)

    return info
