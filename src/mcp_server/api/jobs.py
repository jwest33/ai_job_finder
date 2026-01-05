"""
Jobs API Endpoints

REST endpoints for job browsing and filtering.
"""

import asyncio
import math
from typing import Optional, List, Any
from urllib.parse import unquote

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from dotenv import load_dotenv

from src.core.database import get_database
from src.utils.profile_manager import ProfilePaths
from src.ai import load_threshold_settings

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


def clean_job_dict(job_dict: dict) -> dict:
    """Clean a job dictionary for JSON serialization."""
    float_fields = [
        'salary_min', 'salary_max', 'match_score', 'company_rating',
        'occupation_confidence'
    ]
    for field in float_fields:
        if field in job_dict:
            job_dict[field] = clean_float(job_dict[field])
    return job_dict


class JobResponse(BaseModel):
    """Single job response"""
    job_url: str
    title: Optional[str] = "Unknown Title"
    company: Optional[str] = "Unknown Company"
    location: Optional[str] = "Unknown Location"
    remote: Optional[bool] = None
    source: Optional[str] = "unknown"
    description: Optional[str] = None
    job_type: Optional[str] = None
    date_posted: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    salary_period: Optional[str] = None
    match_score: Optional[float] = None
    match_explanation: Optional[str] = None
    gap_analysis: Optional[str] = None
    resume_suggestions: Optional[str] = None
    is_relevant: Optional[bool] = None
    skills: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    benefits: Optional[List[str]] = None
    work_arrangements: Optional[List[str]] = None
    company_url: Optional[str] = None
    company_industry: Optional[str] = None
    company_size: Optional[str] = None
    company_description: Optional[str] = None
    company_rating: Optional[float] = None
    company_logo_url: Optional[str] = None
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    location_country_code: Optional[str] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    application_status: Optional[str] = None
    applied_at: Optional[str] = None
    application_notes: Optional[str] = None


class PaginatedJobsResponse(BaseModel):
    """Paginated jobs response"""
    items: List[JobResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class JobStatsResponse(BaseModel):
    """Job statistics response"""
    total_jobs: int
    scored_jobs: int
    unscored_jobs: int
    avg_score: float
    high_matches: int
    medium_matches: int
    low_matches: int
    by_source: dict
    # Thresholds used for calculating matches
    thresholds: dict = {"excellent": 80, "good": 60, "fair": 40}


class SourceCount(BaseModel):
    """Source with job count"""
    source: str
    count: int


def _fetch_jobs_sync(
    source, min_score, max_score, remote, location, company, status, search,
    sort_by, sort_order, page, page_size, scored_only
):
    """Synchronous helper to fetch jobs from database. Runs in thread pool."""
    db = get_profile_database()

    # Build query conditions
    conditions = []
    params = []

    if scored_only:
        conditions.append("j.match_score IS NOT NULL")

    if source:
        conditions.append("j.source = ?")
        params.append(source)

    if min_score is not None:
        conditions.append("j.match_score >= ?")
        params.append(min_score)

    if max_score is not None:
        conditions.append("j.match_score <= ?")
        params.append(max_score)

    if remote is not None:
        conditions.append("j.remote = ?")
        params.append(remote)

    if location:
        conditions.append("j.location ILIKE ?")
        params.append(f"%{location}%")

    if company:
        conditions.append("j.company ILIKE ?")
        params.append(f"%{company}%")

    if search:
        conditions.append("(j.title ILIKE ? OR j.company ILIKE ? OR j.description ILIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    if status and status != "not_applied":
        conditions.append("a.status = ?")
        params.append(status)
    elif status == "not_applied":
        conditions.append("a.status IS NULL")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Map sort_by to column
    sort_columns = {
        "date_posted": "j.date_posted",
        "match_score": "j.match_score",
        "first_seen": "j.first_seen",
        "company": "j.company",
        "title": "j.title",
    }
    order_column = sort_columns.get(sort_by, "j.date_posted")

    # Build order clause with secondary sort
    if sort_by == "date_posted":
        if sort_order == "desc":
            order_clause = "j.date_posted DESC NULLS LAST, j.match_score DESC NULLS LAST"
        else:
            order_clause = "j.date_posted ASC NULLS FIRST, j.match_score DESC NULLS LAST"
    elif sort_by == "match_score":
        if sort_order == "desc":
            order_clause = f"{order_column} DESC NULLS LAST"
        else:
            order_clause = f"{order_column} ASC NULLS FIRST"
    else:
        order_clause = f"{order_column} {sort_order.upper()}"

    # Count total
    count_query = f"""
        SELECT COUNT(*) FROM jobs j
        LEFT JOIN job_applications a ON j.job_url = a.job_url
        WHERE {where_clause}
    """
    total = db.fetchone(count_query, tuple(params))[0]

    # Fetch paginated results
    offset = (page - 1) * page_size
    query = f"""
        SELECT
            j.*,
            a.status as application_status,
            a.applied_at,
            a.notes as application_notes
        FROM jobs j
        LEFT JOIN job_applications a ON j.job_url = a.job_url
        WHERE {where_clause}
        ORDER BY {order_clause}
        LIMIT ? OFFSET ?
    """
    params.extend([page_size, offset])

    columns, rows = db.execute_fetch(query, tuple(params))
    return total, columns, rows


@router.get("/", response_model=PaginatedJobsResponse)
async def get_jobs(
    source: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    remote: Optional[bool] = None,
    location: Optional[str] = None,
    company: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    scored_only: bool = False,
    sort_by: str = Query("date_posted", regex="^(date_posted|match_score|first_seen|company|title)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    """
    Get jobs with filtering, sorting, and pagination.
    """
    # Run database query in thread pool to avoid blocking event loop
    total, columns, rows = await asyncio.to_thread(
        _fetch_jobs_sync,
        source, min_score, max_score, remote, location, company, status, search,
        sort_by, sort_order, page, page_size, scored_only
    )

    items = []
    for row in rows:
        job_dict = dict(zip(columns, row))
        # Clean float values (NaN/Infinity -> None)
        job_dict = clean_job_dict(job_dict)
        # Convert arrays from DuckDB format
        for arr_field in ['skills', 'requirements', 'benefits', 'work_arrangements']:
            if job_dict.get(arr_field) is not None:
                job_dict[arr_field] = list(job_dict[arr_field]) if job_dict[arr_field] else []
        # Convert timestamps to ISO format with UTC timezone
        for ts_field in ['first_seen', 'last_seen', 'applied_at']:
            if job_dict.get(ts_field) is not None:
                ts = job_dict[ts_field]
                # Convert to ISO format string with Z suffix for UTC
                if hasattr(ts, 'isoformat'):
                    job_dict[ts_field] = ts.isoformat() + 'Z'
                else:
                    # Already a string, append Z if not present
                    ts_str = str(ts).replace(' ', 'T')
                    if not ts_str.endswith('Z') and '+' not in ts_str:
                        job_dict[ts_field] = ts_str + 'Z'
                    else:
                        job_dict[ts_field] = ts_str
        items.append(JobResponse(**job_dict))

    return PaginatedJobsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


def _fetch_stats_sync():
    """Synchronous helper to fetch job stats. Runs in thread pool."""
    db = get_profile_database()
    thresholds = load_threshold_settings()

    stats = db.fetchone(f"""
        SELECT
            COUNT(*) as total_jobs,
            COUNT(match_score) as scored_jobs,
            COUNT(*) - COUNT(match_score) as unscored_jobs,
            COALESCE(AVG(match_score), 0) as avg_score,
            COUNT(CASE WHEN match_score >= {thresholds.excellent} THEN 1 END) as high_matches,
            COUNT(CASE WHEN match_score >= {thresholds.good} AND match_score < {thresholds.excellent} THEN 1 END) as medium_matches,
            COUNT(CASE WHEN match_score < {thresholds.good} THEN 1 END) as low_matches
        FROM jobs
    """)

    sources = db.fetchall("SELECT source, COUNT(*) as count FROM jobs GROUP BY source")
    by_source = {row[0]: row[1] for row in sources}

    return stats, by_source, thresholds


@router.get("/stats", response_model=JobStatsResponse)
async def get_job_stats():
    """Get job statistics."""
    stats, by_source, thresholds = await asyncio.to_thread(_fetch_stats_sync)

    # Clean avg_score in case of NaN
    avg_score = clean_float(stats[3])
    if avg_score is None:
        avg_score = 0.0

    return JobStatsResponse(
        total_jobs=stats[0],
        scored_jobs=stats[1],
        unscored_jobs=stats[2],
        avg_score=round(avg_score, 1),
        high_matches=stats[4],
        medium_matches=stats[5],
        low_matches=stats[6],
        by_source=by_source,
        thresholds={
            "excellent": thresholds.excellent,
            "good": thresholds.good,
            "fair": thresholds.fair,
        },
    )


def _fetch_sources_sync():
    """Synchronous helper to fetch sources. Runs in thread pool."""
    db = get_profile_database()
    return db.fetchall("SELECT source, COUNT(*) as count FROM jobs GROUP BY source ORDER BY count DESC")


@router.get("/sources", response_model=List[SourceCount])
async def get_sources():
    """Get list of job sources with counts."""
    sources = await asyncio.to_thread(_fetch_sources_sync)
    return [SourceCount(source=row[0], count=row[1]) for row in sources]


def _fetch_single_job_sync(job_url: str):
    """Synchronous helper to fetch a single job. Runs in thread pool."""
    db = get_profile_database()

    query = """
        SELECT
            j.*,
            a.status as application_status,
            a.applied_at,
            a.notes as application_notes
        FROM jobs j
        LEFT JOIN job_applications a ON j.job_url = a.job_url
        WHERE j.job_url = ?
    """

    columns, rows = db.execute_fetch(query, (job_url,))
    row = rows[0] if rows else None
    return columns, row


@router.get("/{job_url:path}", response_model=JobResponse)
async def get_job(job_url: str):
    """Get a single job by URL."""
    decoded_url = unquote(job_url)

    columns, row = await asyncio.to_thread(_fetch_single_job_sync, decoded_url)

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    job_dict = dict(zip(columns, row))

    # Clean float values (NaN/Infinity -> None)
    job_dict = clean_job_dict(job_dict)

    # Convert arrays from DuckDB format
    for arr_field in ['skills', 'requirements', 'benefits', 'work_arrangements']:
        if job_dict.get(arr_field) is not None:
            job_dict[arr_field] = list(job_dict[arr_field]) if job_dict[arr_field] else []

    # Convert timestamps to ISO format with UTC timezone
    for ts_field in ['first_seen', 'last_seen', 'applied_at']:
        if job_dict.get(ts_field) is not None:
            ts = job_dict[ts_field]
            # Convert to ISO format string with Z suffix for UTC
            if hasattr(ts, 'isoformat'):
                job_dict[ts_field] = ts.isoformat() + 'Z'
            else:
                # Already a string, append Z if not present
                ts_str = str(ts).replace(' ', 'T')
                if not ts_str.endswith('Z') and '+' not in ts_str:
                    job_dict[ts_field] = ts_str + 'Z'
                else:
                    job_dict[ts_field] = ts_str

    return JobResponse(**job_dict)
