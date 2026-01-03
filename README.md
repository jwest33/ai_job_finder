# AI Job Finder

Scrape jobs from Indeed & Glassdoor, then match them to your resume using a local VLM, or a service API.
  * Glassdoor searches are relatively slow to avoid aggressive rate limiting
  * Glassdoor schema changes frequently and might result in broken searches

## Quick Start (Docker)

**Prerequisites:** Docker, an OpenAI-compatible API (llama-server, Ollama, OpenAI, etc.)

```bash
# 1. Clone and configure
git clone https://github.com/jwest33/ai_job_finder.git
cd ai_job_finder
cp .env.example .env

# 2. Edit configuration
#    - ai_settings.json: API endpoint and model settings
#    - profiles/default/templates/resume.txt: Your resume
#    - profiles/default/templates/requirements.yaml: Job preferences

# 3. Launch
docker-compose up -d
```

Open http://localhost:3000

## Quick Start (Local)

**Prerequisites:** Python 3.11+, an OpenAI-compatible API

```bash
# 0. Start llama-server, or update the settings for the correct API endpoint 
llama-server --model "D:\models\gemma-3-27b-it\gemma-3-27b-it-UD-Q6_K_XL.gguf" --no-mmap --ctx-size 32768
```

```bash
# 0. Start llama-server for VLM when searching and hitting captchas
llama-server --model "D:\models\gemma-3-27b-it\gemma-3-27b-it-UD-Q6_K_XL.gguf" --mmproj "D:\models\gemma-3-27b-it\mmproj-BF16.gguf" --ctx-size 32768
```

```bash
# 1. Clone and install
git clone https://github.com/jwest33/ai_job_finder.git
cd ai_job_finder
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Mac/Linux
pip install -r requirements.txt

# 2. Initialize and configure
python -m src.cli.main system init
#    - ai_settings.json: API endpoint and model settings
#    - profiles/default/templates/resume.txt: Your resume
#    - profiles/default/templates/requirements.yaml: Job preferences

# 3. Launch web UI
python scripts/start_web.py
```

Open http://localhost:5173

## CLI Usage

```bash
python -m src.cli.main search         # Scrape jobs
python -m src.cli.main match          # Run AI matching
python -m src.cli.main system doctor  # Health check
```

## Proxy Setup (Optional)

For IP rotation during scraping, configure IPRoyal in `.env`:

```env
USE_PROXY=true
IPROYAL_HOST=geo.iproyal.com
IPROYAL_PORT=12321
IPROYAL_USERNAME=your_username
IPROYAL_PASSWORD=your_password
PROXY_ROTATION_COUNT=3
```

## VLM Mode (Optional)

VLM (Visual Language Model) mode uses screen capture and visual automation for Glassdoor scraping. **Only works when running locally** (not in Docker) since it requires desktop display access.

Only enable if Glassdoor starts throwing captchas that block the GraphQL scraper:

```bash
# Install VLM dependencies (local only)
pip install mss pynput
```

```env
USE_VLM_GLASSDOOR=true
```

## License

MIT - See [LICENSE](LICENSE)

Based on [JobSpy](https://github.com/speedyapply/JobSpy) by Cullen Watson.

