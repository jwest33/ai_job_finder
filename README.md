# Job Finding & AI Matching System

AI-powered job hunting automation: scrape jobs from Indeed and Glassdoor, then match them to your resume using local AI.

## Prerequisites

- Python 3.11+
- [llama-server](https://github.com/ggerganov/llama.cpp) (for local AI matching)
- IPRoyal proxy account (optional, for job scraping)

---

## Setup (Local)

### 1. Clone and Install

```bash
git clone https://github.com/jwest33/ai_job_finder.git
cd ai_job_finder

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.venv/scripts/activate
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

- **`.env`** - Credentials and settings
- **`profiles/default/templates/resume.txt`** - Your resume (TXT, PDF, or DOCX)
- **`profiles/default/templates/requirements.yaml`** - Job requirements and preferences

### 4. Start llama-server

```bash
# Start llama-server on localhost:8080 (required for job matching)
llama-server --model /path/to/model.gguf --ctx-size 65536 --cache-type-k q8_0 --cache-type-v q8_0 --port 8080

llama-server --model "D:\models\gemma-3-27b-it\gemma-3-27b-it-UD-Q6_K_XL.gguf" --ctx-size 65536 --cache-type-k q8_0 --cache-type-v q8_0 --no-mapp
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


## 6. Proxy Setup (Optional)

Proxies are **optional** for job scraping. The Indeed scraper works with or without proxies:
- **Without proxy** (`USE_PROXY=false`): Direct API calls from your local network
- **With proxy** (`USE_PROXY=true`): Rotating IPs via IPRoyal for geographic diversity

### Why Use Proxies?

**Benefits:**
- **Geographic diversity**: Different IPs may return location-specific job postings
- **Redundancy**: If one IP fails, others may succeed
- **Multiple perspectives**: Same search from different IPs can reveal different results

**Trade-offs:**
- **Bandwidth costs**: IPRoyal charges for data usage (~50-100KB per 100 results)
- **More duplicates**: 60-75% overlap when using multiple IPs
- **Longer runtime**: Proportional to `PROXY_ROTATION_COUNT`

### IPRoyal Configuration

#### 1. Sign up for IPRoyal

Get residential proxies at [iproyal.com](https://iproyal.com/residential-proxies/)

#### 2. Configure `.env`

```env
# Enable proxy
USE_PROXY=true

# IPRoyal credentials (from your dashboard)
IPROYAL_HOST=geo.iproyal.com
IPROYAL_PORT=12321
IPROYAL_USERNAME=your_username_here
IPROYAL_PASSWORD=your_password_here

# IP rotation (how many different IPs per search)
PROXY_ROTATION_COUNT=3
```

#### 3. Proxy Format & Session-Based Rotation

IPRoyal uses session parameters appended to the **password field**:

**Format:** `http://username:password_country-us_session-{id}_lifetime-30m@host:port`

**Example:**
```
geo.iproyal.com:12321:username:password_country-us_session-abc123_lifetime-30m
```

**Session parameters:**
- `_country-us` - Forces US-based IP addresses
- `_session-{id}` - Unique session ID for IP binding (auto-generated)
- `_lifetime-30m` - Session persists for 30 minutes with same IP

#### 4. IP Rotation Settings

Control how many different IPs to use per search:

```env
PROXY_ROTATION_COUNT=1   # No rotation (single IP per search)
PROXY_ROTATION_COUNT=3   # Each search runs 3x with different IPs (recommended)
PROXY_ROTATION_COUNT=5   # Maximum diversity (higher bandwidth)
```

**Example with rotation:**
- 8 job titles × 1 location × 3 IPs = 24 total searches
- Bandwidth: ~1.2 MB (vs ~0.4 MB without rotation)
- Results: ~250-300 unique jobs (after deduplication from ~1200 raw)

#### 5. Testing Proxy Connection

After configuring `.env`, test your proxy:

```bash
# Activate virtual environment
.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate   # Mac/Linux

# Test proxy connectivity
python test_ip_rotation.py
```

#### 6. Disable Proxy (Use Local Network)

To scrape without proxy:

```env
USE_PROXY=false
```

The scraper will make direct API calls from your local network.

### Bandwidth Estimates

**Per search (50 results):**
- Without proxy: No bandwidth charges (direct API call)
- With proxy: ~55-105 KB per search

**Example scenarios:**
- 8 jobs × 1 location × 1 IP = ~0.4 MB
- 8 jobs × 1 location × 3 IPs = ~1.2 MB
- 8 jobs × 1 location × 5 IPs = ~2.0 MB

### Option 2: MCP-Only Stack

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
python scripts/ai_job_finder.py

# Match jobs with AI (full pipeline)
python scripts/job_matcher.py --input profiles/default/data/jobs_latest.json --full-pipeline

# Or use unified CLI
python -m src.cli.main search          # Quick search
python -m src.cli.main match           # Quick match
python -m src.cli.main system doctor   # Health check
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
Licensed under the MIT License. See [LICENSE-JOBSPY](LICENSE-JOBSPY) for full license text.

Thank you for the excellent foundation!

---

## License

MIT Open License. See [LICENSE](LICENSE).
