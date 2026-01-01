"""
Applications API Endpoints

REST endpoints for tracking job application status.
"""

import asyncio
import math
from typing import Optional, List, Any
from urllib.parse import unquote
from datetime import datetime

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from dotenv import load_dotenv

from src.core.database import get_database

router = APIRouter()


def get_profile_database():
    """Get database for the current active profile, reloading env first."""
    load_dotenv(override=True)
    return get_database()


def clean_float(value: Any) -> Optional[float]:
    """Convert NaN/Infinity to None for JSON serialization."""
    if value is None:
        return None
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


class ApplicationUpdate(BaseModel):
    """Application update request"""
    status: str
    notes: Optional[str] = None
    applied_at: Optional[str] = None
    next_action: Optional[str] = None
    next_action_date: Optional[str] = None


class ApplicationStatsResponse(BaseModel):
    """Application statistics response"""
    total: int
    by_status: dict
    recent_applications: int
    response_rate: float


class JobWithApplication(BaseModel):
    """Job with application details"""
    job_url: str
    title: str
    company: str
    location: str
    remote: bool = False
    source: str
    match_score: Optional[float] = None
    first_seen: str
    application_status: str
    applied_at: Optional[str] = None
    application_notes: Optional[str] = None
    updated_at: Optional[str] = None


class PaginatedApplicationsResponse(BaseModel):
    """Paginated applications response"""
    items: List[JobWithApplication]
    total: int
    page: int
    page_size: int
    total_pages: int


def _fetch_applications_sync(status, sort_by, sort_order, page, page_size):
    """Synchronous helper to fetch applications. Runs in thread pool."""
    db = get_profile_database()

    conditions = ["a.status IS NOT NULL"]
    params = []

    if status:
        conditions.append("a.status = ?")
        params.append(status)

    where_clause = " AND ".join(conditions)

    # Map sort columns
    sort_columns = {
        "updated_at": "a.updated_at",
        "applied_at": "a.applied_at",
        "match_score": "j.match_score",
    }
    order_column = sort_columns.get(sort_by, "a.updated_at")
    order_clause = f"{order_column} {sort_order.upper()} NULLS LAST"

    # Count total
    count_query = f"""
        SELECT COUNT(*) FROM jobs j
        INNER JOIN job_applications a ON j.job_url = a.job_url
        WHERE {where_clause}
    """
    total = db.fetchone(count_query, tuple(params))[0]

    # Fetch paginated results
    offset = (page - 1) * page_size
    query = f"""
        SELECT
            j.job_url,
            j.title,
            j.company,
            j.location,
            j.remote,
            j.source,
            j.match_score,
            j.first_seen,
            a.status as application_status,
            a.applied_at,
            a.notes as application_notes,
            a.updated_at
        FROM jobs j
        INNER JOIN job_applications a ON j.job_url = a.job_url
        WHERE {where_clause}
        ORDER BY {order_clause}
        LIMIT ? OFFSET ?
    """
    params.extend([page_size, offset])

    columns, rows = db.execute_fetch(query, tuple(params))
    return total, columns, rows


@router.get("/", response_model=PaginatedApplicationsResponse)
async def get_applications(
    status: Optional[str] = None,
    sort_by: str = Query("updated_at", regex="^(updated_at|applied_at|match_score)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    """
    Get jobs with application status (excludes not_applied).
    """
    total, columns, rows = await asyncio.to_thread(
        _fetch_applications_sync, status, sort_by, sort_order, page, page_size
    )

    items = []
    for row in rows:
        job_dict = dict(zip(columns, row))
        # Clean float values
        if 'match_score' in job_dict:
            job_dict['match_score'] = clean_float(job_dict['match_score'])
        # Convert timestamps to strings
        for ts_field in ['first_seen', 'applied_at', 'updated_at']:
            if job_dict.get(ts_field) is not None:
                job_dict[ts_field] = str(job_dict[ts_field])
        items.append(JobWithApplication(**job_dict))

    return PaginatedApplicationsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


def _fetch_application_stats_sync():
    """Synchronous helper to fetch application stats. Runs in thread pool."""
    db = get_profile_database()

    # Total applications
    total = db.fetchone("SELECT COUNT(*) FROM job_applications")[0]

    # By status
    status_rows = db.fetchall(
        "SELECT status, COUNT(*) as count FROM job_applications GROUP BY status"
    )
    by_status = {row[0]: row[1] for row in status_rows}

    # Recent applications (last 7 days)
    recent = db.fetchone("""
        SELECT COUNT(*) FROM job_applications
        WHERE applied_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
    """)[0]

    return total, by_status, recent


@router.get("/stats", response_model=ApplicationStatsResponse)
async def get_application_stats():
    """Get application statistics."""
    total, by_status, recent = await asyncio.to_thread(_fetch_application_stats_sync)

    # Response rate (interviewing or better / total applied)
    applied_count = by_status.get('applied', 0)
    positive_responses = sum(
        by_status.get(s, 0)
        for s in ['phone_screen', 'interviewing', 'final_round', 'offer']
    )
    response_rate = (positive_responses / applied_count * 100) if applied_count > 0 else 0

    # Clean float value
    response_rate = clean_float(response_rate)
    if response_rate is None:
        response_rate = 0.0

    return ApplicationStatsResponse(
        total=total,
        by_status=by_status,
        recent_applications=recent,
        response_rate=round(response_rate, 1),
    )


def _update_application_sync(job_url: str, update: ApplicationUpdate):
    """Synchronous helper to update application. Runs in thread pool."""
    db = get_profile_database()

    # Check if job exists
    job = db.fetchone("SELECT job_url FROM jobs WHERE job_url = ?", (job_url,))
    if not job:
        return False

    # Upsert application
    now = datetime.now().isoformat()
    applied_at = update.applied_at if update.applied_at else (now if update.status == 'applied' else None)

    db.execute("""
        INSERT INTO job_applications (job_url, status, notes, applied_at, next_action, next_action_date, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (job_url) DO UPDATE SET
            status = EXCLUDED.status,
            notes = COALESCE(EXCLUDED.notes, job_applications.notes),
            applied_at = COALESCE(EXCLUDED.applied_at, job_applications.applied_at),
            next_action = COALESCE(EXCLUDED.next_action, job_applications.next_action),
            next_action_date = EXCLUDED.next_action_date,
            updated_at = EXCLUDED.updated_at
    """, (
        job_url,
        update.status,
        update.notes,
        applied_at,
        update.next_action,
        update.next_action_date,
        now,
    ))

    return True


@router.put("/{job_url:path}")
async def update_application(job_url: str, update: ApplicationUpdate):
    """Update application status for a job."""
    decoded_url = unquote(job_url)

    success = await asyncio.to_thread(_update_application_sync, decoded_url, update)

    if not success:
        raise HTTPException(status_code=404, detail="Job not found")

    return {"success": True, "message": "Application updated"}
