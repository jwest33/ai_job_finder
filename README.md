# Job Search & Matching System

AI-powered job hunting automation: scrape jobs from Indeed and Glassdoor, then match them to your resume using local AI.

## Prerequisites

- Python 3.11+
- [llama-server](https://github.com/ggerganov/llama.cpp) (for local AI matching)
- Docker & Docker Compose (optional, for containerized deployment)
- IPRoyal proxy account (optional, for job scraping)

---

## Setup (Local)

### 1. Clone and Install

```bash
git clone <repository-url>
cd job_search

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Mac/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Initialize Configuration

```bash
# Initialize project (creates .env and profile structure)
python -m src.cli.main system init
```

### 3. Configure

Edit the following files:

- **`.env`** - Credentials and settings (see `.env.docker.example` for all options)
- **`profiles/default/templates/resume.txt`** - Your resume (TXT, PDF, or DOCX)
- **`profiles/default/templates/requirements.yaml`** - Job requirements and preferences

### 4. Start llama-server

```bash
# Start llama-server on localhost:8080 (required for job matching)
llama-server --model /path/to/model.gguf --ctx-size 8192 --port 8080
```

### 5. Setup Email Delivery (Optional)

Automatically receive job match reports via email using Gmail API.

**Prerequisites:** Google Cloud Console account (free)

```bash
# Run interactive setup wizard
python -m src.utils.email_setup
```

**The wizard will:**
1. Guide you through Google Cloud Console setup (OAuth2 credentials)
2. Configure Gmail API authentication
3. Set email recipients and delivery preferences
4. Test email delivery

**Usage:**
```bash
# Automatic email (if EMAIL_ENABLED=true in .env)
python scripts/job_matcher.py --input profiles/default/data/jobs_latest.json --full-pipeline

# Force email regardless of config
python scripts/job_matcher.py --input profiles/default/data/jobs_latest.json --full-pipeline --email

# Skip email even if enabled
python scripts/job_matcher.py --input profiles/default/data/jobs_latest.json --full-pipeline --no-email
```

---

## Setup (Docker)

### Option 1: Full Stack (with scheduled jobs)

```bash
# Copy and configure environment
cp .env.docker.example .env
# Edit .env with your credentials

# Build and start all services
docker-compose -f docker/docker-compose.yml up -d

# View logs
docker-compose -f docker/docker-compose.yml logs -f

# Stop services
docker-compose -f docker/docker-compose.yml down
```

**Services included:**
- MCP Server (port 3000)
- Web UI (port 5000)
- Scheduled job scraping (configurable cron)
- Scheduled job matching (configurable cron)

### Option 2: MCP-Only Stack

```bash
# Copy and configure environment
cp .env.docker.example .env
# Edit .env with your credentials

# Build and start MCP services only
docker-compose -f docker/docker-compose.mcp.yml up -d

# View logs
docker-compose -f docker/docker-compose.mcp.yml logs -f

# Stop services
docker-compose -f docker/docker-compose.mcp.yml down
```

**Services included:**
- MCP Server (port 3000)
- Web UI (port 5000)
- No background cron jobs (manual execution only)

---

## Running the Application

### Local

```bash
# Activate virtual environment first
.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate   # Mac/Linux

# Run job search
python scripts/job_search.py

# Match jobs with AI (full pipeline)
python scripts/job_matcher.py --input profiles/default/data/jobs_latest.json --full-pipeline

# Or use unified CLI
python -m src.cli.main search          # Quick search
python -m src.cli.main match           # Quick match
python -m src.cli.main system doctor   # Health check
```

### Docker (Full Stack)

```bash
# Use CLI from container
docker exec -it job-search-app python -m src.cli.main search
docker exec -it job-search-app python -m src.cli.main match

# Or run scripts directly
docker exec -it job-search-app python scripts/job_search.py
docker exec -it job-search-app python scripts/job_matcher.py --input profiles/default/data/jobs_latest.json --full-pipeline
```

### Docker (MCP-Only Stack)

```bash
# Access web UI
open http://localhost:5000

# Use CLI from container
docker exec -it job-search-mcp python -m src.cli.main search
docker exec -it job-search-mcp python -m src.cli.main match
```

---

## Output

### Job Scraper
- **CSV/JSON**: `profiles/default/data/jobs_latest.{csv,json}`
- **Archives**: `profiles/default/data/jobs_indeed_YYYYMMDD_HHMMSS.json`

### Job Matcher
- **Matched Jobs**: `profiles/default/data/jobs_matched_YYYYMMDD_HHMMSS.json`
- **HTML Report**: `profiles/default/reports/job_report_YYYYMMDD_HHMMSS.html`
- **Tracking DB**: `profiles/default/data/job_tracker.db`

---

## Features

**Job Scraper:**
- Indeed & Glassdoor GraphQL APIs (no rate limits)
- IPRoyal proxy rotation (optional)
- Batch searches across titles/locations
- Automatic deduplication

**Job Matcher:**
- 3-pass AI analysis (scoring, gap analysis, optimization)
- Multi-threaded processing (4x-8x faster)
- Checkpoint/resume capability
- SQLite tracking (no duplicate processing)
- HTML reports with collapsible sections
- Local AI (llama-server) - complete privacy

---

## Acknowledgments

Job scraping functionality is based on [JobSpy](https://github.com/speedyapply/JobSpy) by Cullen Watson (speedyapply).

Copyright (c) 2023 Cullen Watson
Licensed under the MIT License. See [LICENSE-JOBSPY.txt](LICENSE-JOBSPY.txt) for full license text.

Thank you for the excellent foundation!

---

## License

For personal/educational use only.
