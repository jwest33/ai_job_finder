"""
API Router Registration

Mounts all API endpoints under /api/v1/
"""

from fastapi import APIRouter

from .jobs import router as jobs_router
from .applications import router as applications_router
from .attachments import router as attachments_router
from .templates import router as templates_router
from .scraper import router as scraper_router
from .system import router as system_router
from .ai import router as ai_router

# Create main API router
api_router = APIRouter(prefix="/api/v1")

# Include all sub-routers
api_router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
api_router.include_router(applications_router, prefix="/applications", tags=["applications"])
api_router.include_router(attachments_router, prefix="/attachments", tags=["attachments"])
api_router.include_router(templates_router, prefix="/templates", tags=["templates"])
api_router.include_router(scraper_router, prefix="/scraper", tags=["scraper"])
api_router.include_router(system_router, prefix="/system", tags=["system"])
api_router.include_router(ai_router, prefix="/ai", tags=["ai"])
