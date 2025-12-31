# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered job hunting automation system that scrapes jobs from Indeed and Glassdoor, then matches them against a resume and requirements using local AI (llama-server). Jobs are stored in DuckDB, scored through a 3-pass AI pipeline, and results are delivered via HTML reports or email.

## Common Commands

```bash
# Activate virtual environment (Windows)
.venv\Scripts\Activate.ps1

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

# Start MCP server (FastAPI on port 3000)
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
│   ├── database.py    # DuckDB connection management
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
├── mcp_server/        # FastAPI MCP server
│   ├── server.py      # Main FastAPI app (tool/resource dispatch)
│   ├── tools/         # Tool handlers (scraper, matcher, email, etc.)
│   └── resources/     # Resource providers (profile, jobs, config)
│
├── cli/               # Click-based CLI
│   └── main.py        # Main CLI entry point with command groups
│
└── utils/
    └── profile_manager.py  # Multi-profile support
```

### Data Flow

1. **Scraping**: `src/core/scraper.py` → site scrapers → `JobStorage` → DuckDB
2. **Matching**: `JobMatcherPipeline` in `scripts/job_matcher.py` orchestrates 3-pass AI pipeline
3. **Storage**: Jobs stored in `profiles/<profile>/data/jobs.duckdb`
4. **Reports**: HTML generated to `profiles/<profile>/reports/`

### Profile System

All data is profile-isolated under `profiles/<name>/`:
- `templates/resume.txt` - Plain text resume
- `templates/requirements.yaml` - Job requirements and preferences
- `data/jobs.duckdb` - DuckDB database
- `data/job_tracker.db` - SQLite tracking DB
- `reports/` - Generated HTML reports

Active profile set via `ACTIVE_PROFILE` in `.env`. Use `ProfilePaths` class for path resolution.

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

## Configuration

Key `.env` variables:
- `LLAMA_SERVER_URL` - llama-server endpoint (default: `http://localhost:8080`)
- `MIN_MATCH_SCORE` - Minimum score threshold (default: 60)
- `ACTIVE_PROFILE` - Current profile name (default: `default`)
- `EMAIL_ENABLED` - Auto-send reports via Gmail API
- `USE_PROXY` / `IPROYAL_*` - Proxy configuration for scraping

## Dependencies

Main dependencies: `duckdb`, `pandas`, `pydantic`, `click`, `rich`, `fastapi`, `jinja2`, `pyyaml`
AI: Requires external llama-server running with appropriate GGUF model
