"""
Scraper API Endpoints

REST endpoints for job search and AI matching.
"""

import asyncio
import uuid
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from src.utils.profile_manager import ProfilePaths, get_active_profile

router = APIRouter()


def get_current_profile_paths() -> ProfilePaths:
    """Get ProfilePaths for the current active profile."""
    return ProfilePaths()  # Uses get_active_profile() internally


# Simple in-memory task storage
# In production, use Redis or database
_tasks = {}


class SearchRequest(BaseModel):
    """Search request parameters"""
    jobs: List[str]
    locations: List[str] = ["Remote"]
    results_per_search: int = 50
    scrapers: List[str] = ["indeed", "glassdoor"]


class MatchRequest(BaseModel):
    """Match pipeline request parameters"""
    source: Optional[str] = None
    min_score: int = 60
    full_pipeline: bool = True


class TaskProgress(BaseModel):
    """Task progress info"""
    current: int
    total: int
    message: Optional[str] = None


class TaskStatus(BaseModel):
    """Task status response"""
    task_id: str
    status: str  # pending, running, completed, failed
    progress: Optional[TaskProgress] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class ScraperConfig(BaseModel):
    """Scraper configuration"""
    search_terms: List[str]
    locations: List[str]
    scrapers: List[str]
    results_per_search: int


def create_task(task_type: str) -> str:
    """Create a new task and return its ID."""
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "id": task_id,
        "type": task_type,
        "status": "pending",
        "progress": None,
        "result": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
    }
    return task_id


def update_task(task_id: str, **kwargs):
    """Update task status."""
    if task_id in _tasks:
        _tasks[task_id].update(kwargs)


def get_task(task_id: str) -> Optional[dict]:
    """Get task by ID."""
    return _tasks.get(task_id)


def _scrape_single_search(source: str, job_title: str, location: str, results_per_search: int, proxies, use_proxy: bool):
    """Scrape a single search and return jobs list (no DB writes)."""
    import random
    import string
    from src.core.scraper import scrape_jobs
    from src.core.models import JobPost

    # Generate session ID for IP rotation
    proxy_session = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) if use_proxy else None

    try:
        df = scrape_jobs(
            site_name=source,
            search_term=job_title,
            location=location,
            results_wanted=results_per_search,
            proxies=proxies,
            use_proxies=use_proxy,
            proxy_session=proxy_session
        )

        if not df.empty:
            jobs = []
            for _, row in df.iterrows():
                try:
                    job = JobPost(**row.to_dict())
                    jobs.append((source, job))
                except Exception:
                    pass
            return jobs
    except Exception as e:
        print(f"Search error for {source}/{job_title}/{location}: {e}")

    return []


def _run_full_search_pipeline(task_id: str, params, profile_name: str):
    """
    Run all searches in parallel using ThreadPoolExecutor, collect results in memory,
    then batch write to database.
    """
    import os
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from dotenv import load_dotenv
    from src.core.storage import JobStorage

    load_dotenv(override=True)

    # Get proxy configuration once
    use_proxy = os.getenv("USE_PROXY", "false").lower() == "true"
    proxy_url = os.getenv("PROXY_URL")
    proxies = [proxy_url] if (use_proxy and proxy_url) else None

    if use_proxy:
        print(f"[DEBUG] Using proxy: {proxy_url[:50]}..." if proxy_url else "[DEBUG] Proxy enabled but no PROXY_URL set")

    # Build list of all searches to run
    searches = []
    for job_title in params.jobs:
        for location in params.locations:
            for source in params.scrapers:
                searches.append((source, job_title, location))

    total_searches = len(searches)
    update_task(task_id, progress={
        "current": 0,
        "total": total_searches,
        "message": f"Starting {total_searches} parallel searches..."
    })

    # Run all searches in parallel, collect results in memory
    all_jobs = []  # List of (source, JobPost) tuples
    completed = 0

    # Use up to 4 workers for parallel scraping
    max_workers = min(4, total_searches)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_search = {
            executor.submit(
                _scrape_single_search,
                source, job_title, location, params.results_per_search, proxies, use_proxy
            ): (source, job_title, location)
            for source, job_title, location in searches
        }

        for future in as_completed(future_to_search):
            source, job_title, location = future_to_search[future]
            completed += 1

            try:
                jobs = future.result()
                all_jobs.extend(jobs)
                print(f"[INFO] {source}/{job_title}/{location}: found {len(jobs)} jobs")
            except Exception as e:
                print(f"[ERROR] {source}/{job_title}/{location}: {e}")

            update_task(task_id, progress={
                "current": completed,
                "total": total_searches,
                "message": f"Completed {completed}/{total_searches} searches ({len(all_jobs)} jobs found)"
            })

    # Batch write all jobs to database by source
    update_task(task_id, progress={
        "current": total_searches,
        "total": total_searches,
        "message": f"Saving {len(all_jobs)} jobs to database..."
    })

    storage = JobStorage(profile_name=profile_name)

    # Group jobs by source
    jobs_by_source = {}
    for source, job in all_jobs:
        if source not in jobs_by_source:
            jobs_by_source[source] = []
        jobs_by_source[source].append(job)

    # Save each source batch using TRUE batch operations (single connection)
    for source, jobs in jobs_by_source.items():
        if jobs:
            result = storage.save_jobs_batch(jobs, source=source)
            print(f"[INFO] Saved {result.get('saved', 0)} new, updated {result.get('updated', 0)} from {source}")

    return len(all_jobs)


async def run_search_task(task_id: str, params: SearchRequest):
    """Run job search in background."""
    try:
        update_task(task_id, status="running")

        print(f"[DEBUG] Search params received:")
        print(f"[DEBUG]   jobs: {params.jobs} (count: {len(params.jobs)})")
        print(f"[DEBUG]   locations: {params.locations}")
        print(f"[DEBUG]   scrapers: {params.scrapers}")

        current_profile = get_active_profile()

        # Run entire search pipeline in one thread
        total_jobs_found = await asyncio.to_thread(
            _run_full_search_pipeline,
            task_id, params, current_profile
        )

        update_task(task_id,
            status="completed",
            result={"jobs_found": total_jobs_found, "profile": current_profile},
            progress={"current": 100, "total": 100, "message": "Complete"}
        )

    except Exception as e:
        update_task(task_id, status="failed", error=str(e))


def _clean_job_dict(job: dict) -> dict:
    """Convert numpy arrays to Python lists and clean NaN values for scoring."""
    import numpy as np
    import math

    cleaned = {}
    for key, value in job.items():
        # Convert numpy arrays to Python lists
        if isinstance(value, np.ndarray):
            cleaned[key] = value.tolist()
        # Convert NaN/None floats
        elif isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            cleaned[key] = None
        # Convert numpy scalar types
        elif hasattr(value, 'item'):
            cleaned[key] = value.item()
        else:
            cleaned[key] = value
    return cleaned


def _run_full_match_pipeline(task_id: str, profile_name: str, source: Optional[str], min_score: int):
    """
    Run the entire matching pipeline using the exact same JobMatcherPipeline as CLI.
    """
    import os
    import sys
    from pathlib import Path
    from dotenv import load_dotenv

    # Load .env to ensure MATCH_THREADS and other settings are available
    load_dotenv(override=True)

    # Ensure prints are flushed immediately in thread pool
    def log(msg):
        print(msg, flush=True)

    # Log the thread limit being used
    match_threads = os.getenv("MATCH_THREADS", "4")
    log(f"[API] Using MATCH_THREADS={match_threads}")

    # Add project root to path if needed
    project_root = Path(__file__).parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Import the CLI's pipeline - this is the exact same code the CLI uses
    from scripts.job_matcher import JobMatcherPipeline

    update_task(task_id, progress={"current": 5, "total": 100, "message": "Initializing pipeline..."})

    # Create pipeline with batch queue mode enabled (same as CLI default)
    pipeline = JobMatcherPipeline(
        enable_checkpoints=False,  # Don't use checkpoints for web API
        enable_email=False,  # Don't send emails from web API
        use_batch_queue=True  # Use batch queue for GPU efficiency
    )

    # Load resume and requirements (REQUIRED before load_jobs_from_db)
    log("[API] Loading resume and requirements...")
    update_task(task_id, progress={"current": 8, "total": 100, "message": "Loading resume and requirements..."})
    if not pipeline.analyzer.load_all():
        log("[API] Failed to load resume and requirements")
        return 0, "Failed to load resume and requirements"
    log("[API] Resume and requirements loaded")

    # Test llama-server connection
    log("[API] Testing llama-server connection...")
    update_task(task_id, progress={"current": 10, "total": 100, "message": "Connecting to AI server..."})
    if not pipeline.client.test_connection():
        log(f"[API] Failed to connect to llama-server at {pipeline.client.server_url}")
        return 0, f"Failed to connect to llama-server at {pipeline.client.server_url}"
    log("[API] Connected to llama-server")

    update_task(task_id, progress={"current": 15, "total": 100, "message": "Loading jobs from database..."})
    log(f"[API] Loading jobs from database (source: {source or 'indeed'})...")

    # Load jobs from database (same as CLI)
    jobs = pipeline.load_jobs_from_db(source or "indeed")

    if not jobs:
        log("[API] No unprocessed jobs found")
        return 0, "No unprocessed jobs found"

    total_jobs = len(jobs)
    log(f"[API] Loaded {total_jobs} jobs")
    update_task(task_id, progress={"current": 20, "total": total_jobs, "message": f"Loaded {total_jobs} jobs"})

    # Run scoring pass (same as CLI) with progress callback
    log(f"[API] Starting scoring pass for {total_jobs} jobs...")

    def api_progress_callback(current: int, total: int, message: str):
        """Update API task with real-time scoring progress"""
        update_task(task_id, progress={
            "current": current,
            "total": total,
            "message": message
        })

    matched_jobs = pipeline.run_scoring_pass(jobs, min_score, api_progress_callback=api_progress_callback)
    log(f"[API] Scoring complete: {len(matched_jobs)} matched jobs")

    # Save results to database
    log("[API] Saving results to database...")
    update_task(task_id, progress={"current": total_jobs, "total": total_jobs, "message": "Saving results..."})

    if matched_jobs:
        pipeline.save_matched_jobs(matched_jobs)
        log(f"[API] Saved {len(matched_jobs)} matched jobs")

    update_task(task_id, progress={"current": total_jobs, "total": total_jobs, "message": "Complete"})
    log("[API] Pipeline complete")

    return len(matched_jobs), None


async def run_match_task(task_id: str, params: MatchRequest):
    """Run AI matching pipeline in background."""
    try:
        current_profile = get_active_profile()

        update_task(task_id, status="running", progress={
            "current": 0,
            "total": 100,
            "message": f"Starting matching pipeline for profile '{current_profile}'..."
        })

        # Run entire pipeline in a single thread - no per-job async overhead
        processed, error = await asyncio.to_thread(
            _run_full_match_pipeline,
            task_id, current_profile, params.source, params.min_score
        )

        if error:
            update_task(task_id,
                status="completed",
                result={"jobs_processed": 0, "message": error, "profile": current_profile},
                progress={"current": 100, "total": 100, "message": "Complete"}
            )
        else:
            update_task(task_id,
                status="completed",
                result={"jobs_processed": processed, "profile": current_profile},
                progress={"current": 100, "total": 100, "message": "Complete"}
            )

    except Exception as e:
        update_task(task_id, status="failed", error=str(e))


@router.post("/search")
async def start_search(request: SearchRequest):
    """Start a new job search."""
    task_id = create_task("search")

    # Run in background
    asyncio.create_task(run_search_task(task_id, request))

    return {"task_id": task_id}


@router.get("/search/{task_id}/status", response_model=TaskStatus)
async def get_search_status(task_id: str):
    """Get search task status."""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatus(
        task_id=task["id"],
        status=task["status"],
        progress=TaskProgress(**task["progress"]) if task["progress"] else None,
        result=task["result"],
        error=task["error"],
    )


@router.post("/match")
async def start_matching(request: MatchRequest):
    """Start AI matching pipeline."""
    task_id = create_task("match")

    # Run in background
    asyncio.create_task(run_match_task(task_id, request))

    return {"task_id": task_id}


@router.get("/match/{task_id}/status", response_model=TaskStatus)
async def get_match_status(task_id: str):
    """Get match task status."""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatus(
        task_id=task["id"],
        status=task["status"],
        progress=TaskProgress(**task["progress"]) if task["progress"] else None,
        result=task["result"],
        error=task["error"],
    )


@router.get("/config", response_model=ScraperConfig)
async def get_config():
    """Get scraper configuration from requirements."""
    import yaml

    paths = get_current_profile_paths()

    config = {
        "search_terms": [],
        "locations": ["Remote"],
        "scrapers": ["indeed", "glassdoor"],
        "results_per_search": 50,
    }

    # Try to load from requirements
    if paths.requirements_path.exists():
        try:
            content = paths.requirements_path.read_text(encoding='utf-8')
            data = yaml.safe_load(content)

            if isinstance(data, dict):
                job_req = data.get('job_requirements', {})
                # Check for search terms in order of preference
                if 'search_jobs' in job_req:
                    config['search_terms'] = job_req['search_jobs']
                elif 'search_terms' in job_req:
                    config['search_terms'] = job_req['search_terms']
                elif 'target_roles' in job_req:
                    config['search_terms'] = job_req['target_roles']

                prefs = data.get('preferences', {})
                if 'locations' in prefs:
                    config['locations'] = prefs['locations']

        except Exception:
            pass

    return ScraperConfig(**config)
