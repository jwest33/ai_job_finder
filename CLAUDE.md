# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered job hunting automation system that scrapes jobs from Indeed and Glassdoor, then matches them against a resume and requirements using local AI (llama-server). Jobs are stored in DuckDB, scored through a 3-pass AI pipeline, and results are delivered via a React web UI, HTML reports, or email.

## Common Commands

```bash
# Activate virtual environment (Windows)
.venv\Scripts\Activate.ps1

# Start web app (backend API + React frontend)
python scripts/start_web.py

# Run job search (scrapes Indeed & Glassdoor)
python scripts/ai_job_finder.py
python -m src.cli.main search

# Run full matching pipeline (score -> analyze -> optimize -> report)
python scripts/job_matcher.py --input profiles/default/data/jobs_latest.json --full-pipeline
python -m src.cli.main match

# Process all job sources (Indeed, Glassdoor, etc.)
python scripts/job_matcher.py --all-sources --full-pipeline

# System health check
python -m src.cli.main system doctor

# Initialize project (creates .env and profile structure)
python -m src.cli.main system init

# View tracker statistics
python -m src.cli.main stats

# Start MCP server only (FastAPI on port 3000)
python -m src.mcp_server.server

# Email setup wizard
python -m src.utils.email_setup
```

## Architecture

### Core Components

```
src/
├── core/              # Job scraping infrastructure
│   ├── scraper.py     # Main scraper orchestrator (concurrent scraping)
│   ├── storage.py     # JobStorage class - DuckDB interface
│   ├── database.py    # DuckDB connection management (singleton per profile)
│   ├── models.py      # JobPost Pydantic model
│   └── scrapers/      # Site-specific scrapers (Indeed, Glassdoor)
│
├── job_matcher/       # AI matching pipeline
│   ├── llama_client.py       # Local AI server client (llama-server)
│   ├── match_scorer.py       # Pass 1: Score jobs (0-100)
│   ├── gap_analyzer.py       # Pass 2: Analyze strengths/gaps
│   ├── resume_optimizer.py   # Pass 3: Resume recommendations
│   ├── job_tracker.py        # SQLite tracking (prevents reprocessing)
│   ├── checkpoint_manager.py # Checkpoint/resume for long runs
│   ├── failure_tracker.py    # Track and retry failed jobs
│   └── report_generator.py   # HTML report generation
│
├── mcp_server/        # FastAPI backend
│   ├── server.py      # Main FastAPI app with CORS
│   ├── api/           # REST API routers
│   │   ├── jobs.py        # Job listing, filtering, sorting
│   │   ├── templates.py   # Resume/requirements CRUD
│   │   ├── system.py      # Profiles, health checks
│   │   ├── scraper.py     # Search and match tasks
│   │   └── applications.py # Application status tracking
│   ├── tools/         # MCP tool handlers
│   └── resources/     # MCP resource providers
│
├── cli/               # Click-based CLI
│   └── main.py        # Main CLI entry point with command groups
│
└── utils/
    └── profile_manager.py  # Multi-profile support with get_active_profile()

web/                   # React frontend (Vite + TypeScript)
├── src/
│   ├── api/           # API client functions
│   ├── components/    # React components
│   │   ├── common/    # Reusable UI components
│   │   ├── jobs/      # Job card, filters, score badge
│   │   └── layout/    # Header, sidebar, profile selector
│   ├── pages/         # Page components (Jobs, Templates, Search, etc.)
│   ├── store/         # Zustand stores (jobStore, uiStore)
│   └── types/         # TypeScript interfaces
└── package.json

scripts/
└── start_web.py       # Starts both backend (port 3000) and frontend (port 5173)
```

### Data Flow

1. **Scraping**: `src/core/scraper.py` → site scrapers → `JobStorage` → DuckDB
2. **Matching**: `JobMatcherPipeline` in `scripts/job_matcher.py` orchestrates 3-pass AI pipeline
3. **Storage**: Jobs stored in `profiles/<profile>/data/jobs.duckdb`
4. **Reports**: HTML generated to `profiles/<profile>/reports/`
5. **Web UI**: React frontend fetches from FastAPI backend, displays jobs with filtering/sorting

### Profile System

All data is profile-isolated under `profiles/<name>/`:
- `templates/resume.txt` - Plain text resume
- `templates/requirements.yaml` - Job requirements and preferences
- `data/jobs.duckdb` - DuckDB database
- `data/job_tracker.db` - SQLite tracking DB
- `reports/` - Generated HTML reports

**Profile Resolution**: Use `get_active_profile()` from `profile_manager.py` - it reads directly from the `.env` file to avoid caching issues with `os.getenv()`. The `ProfilePaths` class uses this internally.

**Profile Switching**: When switching profiles via API (`POST /api/v1/system/profiles/{name}/activate`):
1. Updates `ACTIVE_PROFILE` in `.env` file
2. Calls `DatabaseManager.close_all()` to clear connection cache
3. Frontend invalidates all react-query caches and refetches Zustand store

### REST API Endpoints

Base URL: `http://localhost:3000/api/v1`

**Jobs** (`/jobs`):
- `GET /` - List jobs with filtering, sorting, pagination
  - Query params: `source`, `min_score`, `remote`, `status`, `search`, `sort_by`, `sort_order`, `page`, `page_size`
  - Default sort: `date_posted` DESC with secondary `match_score` DESC
- `GET /{job_url}` - Get single job details
- `GET /sources` - List available job sources with counts
- `GET /stats` - Job statistics (counts, averages)

**Templates** (`/templates`):
- `GET /resume` - Get current profile's resume
- `PUT /resume` - Update resume content
- `GET /requirements` - Get current profile's requirements
- `PUT /requirements` - Update requirements (validates YAML)
- `POST /validate` - Validate both templates

**System** (`/system`):
- `GET /health` - Health check with component status
- `GET /profiles` - List all profiles
- `POST /profiles/{name}/activate` - Switch active profile
- `GET /debug/profile-state` - Debug endpoint showing current profile, paths, job count

**Scraper** (`/scraper`):
- `POST /search` - Start async job search task
- `GET /search/{task_id}/status` - Get search task progress
- `POST /match` - Start async matching pipeline
- `GET /match/{task_id}/status` - Get match task progress
- `GET /config` - Get scraper config from requirements

**Applications** (`/applications`):
- `GET /` - List applications by status
- `PUT /{job_url}` - Update application status/notes
- `GET /stats` - Application statistics

### AI Pipeline (3-Pass)

1. **Scoring** (`MatchScorer`): Deterministic filters + AI scoring (0-100)
2. **Gap Analysis** (`GapAnalyzer`): Identify strengths and missing requirements
3. **Optimization** (`ResumeOptimizer`): Generate resume keyword suggestions

Each pass uses `LlamaClient` to communicate with local llama-server. Batch processing with `SmoothBatchProcessor` for GPU efficiency.

### Key Patterns

- **Concurrent scraping**: `ThreadPoolExecutor` in `scraper.py`
- **Batch AI processing**: Queue-based processing in `smooth_batch_processor.py`
- **Checkpoint/resume**: Long pipelines can resume from failure via `CheckpointManager`
- **Failure tracking**: `FailureTracker` records errors for retry with `--retry-failed`
- **Database singleton**: `DatabaseManager` maintains one connection per profile, cleared on profile switch
- **Profile isolation**: All file paths resolved via `ProfilePaths` using `get_active_profile()`
- **Frontend state**: Jobs use Zustand store (`jobStore`), other data uses react-query

### Frontend Patterns

- **React Query**: Used for templates, profiles, stats - auto-refetches on invalidation
- **Zustand Store**: Used for jobs list - must call `fetchJobs()` explicitly on profile change
- **Profile Switch**: `ProfileSelector` component invalidates all queries AND calls `resetFilters()`/`fetchJobs()` on Zustand store

## Configuration

Key `.env` variables:
- `LLAMA_SERVER_URL` - llama-server endpoint (default: `http://localhost:8080`)
- `MIN_MATCH_SCORE` - Minimum score threshold (default: 60)
- `ACTIVE_PROFILE` - Current profile name (default: `default`)
- `EMAIL_ENABLED` - Auto-send reports via Gmail API
- `USE_PROXY` / `IPROYAL_*` - Proxy configuration for scraping

## Dependencies

**Backend**: `duckdb`, `pandas`, `pydantic`, `click`, `rich`, `fastapi`, `uvicorn`, `jinja2`, `pyyaml`, `python-dotenv`

**Frontend**: `react`, `react-router-dom`, `@tanstack/react-query`, `zustand`, `tailwindcss`, `lucide-react`, `date-fns`

**AI**: Requires external llama-server running with appropriate GGUF model
