#!/bin/bash
# =============================================================================
# Docker Entrypoint Script for Job Search Application
# =============================================================================
# This script:
# 1. Sets up cron jobs based on environment variables
# 2. Starts the cron daemon
# 3. Tails logs for Docker output
# 4. Supports manual execution mode

set -e

# Default cron schedules (if not provided via environment)
CRON_SCHEDULE_SCRAPER="${CRON_SCHEDULE_SCRAPER:-0 9 * * *}"
CRON_SCHEDULE_MATCHER="${CRON_SCHEDULE_MATCHER:-30 9 * * *}"
ENABLE_SCRAPER_CRON="${ENABLE_SCRAPER_CRON:-true}"
ENABLE_MATCHER_CRON="${ENABLE_MATCHER_CRON:-true}"

# Profile configuration
ACTIVE_PROFILE="${ACTIVE_PROFILE:-default}"
PROFILE_DIR="/app/profiles/${ACTIVE_PROFILE}"

# MCP service configuration
MCP_SERVER_ENABLED="${MCP_SERVER_ENABLED:-true}"
MCP_WEB_CLIENT_ENABLED="${MCP_WEB_CLIENT_ENABLED:-true}"
MCP_SERVER_PORT="${MCP_SERVER_PORT:-3000}"
MCP_WEB_CLIENT_PORT="${MCP_WEB_CLIENT_PORT:-5000}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Job Search Docker Container Starting${NC}"
echo -e "${BLUE}========================================${NC}"

# Function to log with timestamp
log() {
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Function to setup cron jobs
setup_cron() {
    log "${GREEN}Setting up cron jobs...${NC}"

    # Clear any existing crontab
    > /etc/cron.d/job-search

    # Add environment variables to cron environment
    log "Exporting environment variables to cron..."
    printenv | grep -v "no_proxy" >> /etc/cron.d/job-search

    # Add scraper cron job if enabled
    if [ "$ENABLE_SCRAPER_CRON" = "true" ]; then
        log "${GREEN}Job Scraper: Enabled${NC}"
        log "  Schedule: ${CRON_SCHEDULE_SCRAPER}"
        log "  Profile: ${ACTIVE_PROFILE}"
        echo "${CRON_SCHEDULE_SCRAPER} root cd /app && /usr/local/bin/python scripts/job_search.py --profile ${ACTIVE_PROFILE} >> /var/log/job-search/scraper.log 2>&1" >> /etc/cron.d/job-search
    else
        log "${YELLOW}Job Scraper: Disabled${NC}"
    fi

    # Add matcher cron job if enabled
    if [ "$ENABLE_MATCHER_CRON" = "true" ]; then
        log "${GREEN}Job Matcher: Enabled${NC}"
        log "  Schedule: ${CRON_SCHEDULE_MATCHER}"
        log "  Profile: ${ACTIVE_PROFILE}"
        echo "${CRON_SCHEDULE_MATCHER} root cd /app && /usr/local/bin/python scripts/job_matcher.py --profile ${ACTIVE_PROFILE} --input ${PROFILE_DIR}/data/jobs_latest.json --full-pipeline >> /var/log/job-search/matcher.log 2>&1" >> /etc/cron.d/job-search
    else
        log "${YELLOW}Job Matcher: Disabled${NC}"
    fi

    # Set permissions
    chmod 0644 /etc/cron.d/job-search

    # Load crontab
    crontab /etc/cron.d/job-search

    log "${GREEN}Cron setup complete${NC}"
}

# Function to test configuration
test_config() {
    log "${BLUE}Testing configuration...${NC}"

    # Check if .env exists
    if [ ! -f "/app/.env" ]; then
        log "${RED}ERROR: .env file not found!${NC}"
        log "${YELLOW}Please mount your .env file to /app/.env${NC}"
        exit 1
    fi

    # Check if profile directory exists
    if [ ! -d "${PROFILE_DIR}" ]; then
        log "${RED}ERROR: Profile directory not found: ${PROFILE_DIR}${NC}"
        log "${YELLOW}Please ensure profiles are mounted to /app/profiles${NC}"
        log "${YELLOW}Active profile: ${ACTIVE_PROFILE}${NC}"
        exit 1
    fi

    # Check if profile templates directory exists
    if [ ! -d "${PROFILE_DIR}/templates" ]; then
        log "${YELLOW}WARNING: templates/ directory not found in profile: ${ACTIVE_PROFILE}${NC}"
        log "${YELLOW}Expected location: ${PROFILE_DIR}/templates${NC}"
    fi

    # Check if resume exists in profile
    if [ ! -f "${PROFILE_DIR}/templates/resume.txt" ]; then
        log "${YELLOW}WARNING: resume.txt not found in profile templates${NC}"
        log "${YELLOW}Expected location: ${PROFILE_DIR}/templates/resume.txt${NC}"
    fi

    # Check if requirements.yaml exists in profile
    if [ ! -f "${PROFILE_DIR}/templates/requirements.yaml" ]; then
        log "${YELLOW}WARNING: requirements.yaml not found in profile templates${NC}"
        log "${YELLOW}Expected location: ${PROFILE_DIR}/templates/requirements.yaml${NC}"
    fi

    # Check if profile data directory is writable
    if [ ! -d "${PROFILE_DIR}/data" ]; then
        log "${YELLOW}WARNING: Creating data directory for profile: ${PROFILE_DIR}/data${NC}"
        mkdir -p "${PROFILE_DIR}/data"
    fi

    if [ ! -w "${PROFILE_DIR}/data" ]; then
        log "${RED}ERROR: Profile data directory is not writable: ${PROFILE_DIR}/data${NC}"
        exit 1
    fi

    # Check llama-server connectivity (if matcher is enabled)
    if [ "$ENABLE_MATCHER_CRON" = "true" ]; then
        LLAMA_SERVER_URL="${LLAMA_SERVER_URL:-http://localhost:8080}"
        log "Testing llama-server connection at ${LLAMA_SERVER_URL}..."
        if curl -s --max-time 5 "${LLAMA_SERVER_URL}/health" > /dev/null 2>&1; then
            log "${GREEN}llama-server is reachable${NC}"
        else
            log "${YELLOW}WARNING: Cannot reach llama-server at ${LLAMA_SERVER_URL}${NC}"
            log "${YELLOW}Job matcher may fail when scheduled${NC}"
        fi
    fi

    log "${GREEN}Configuration test complete${NC}"
}

# Function to show current configuration
show_config() {
    echo ""
    log "${BLUE}Current Configuration:${NC}"
    log "  Active Profile: ${ACTIVE_PROFILE}"
    log "  Profile Directory: ${PROFILE_DIR}"
    log "  Scraper Enabled: ${ENABLE_SCRAPER_CRON}"
    log "  Scraper Schedule: ${CRON_SCHEDULE_SCRAPER}"
    log "  Matcher Enabled: ${ENABLE_MATCHER_CRON}"
    log "  Matcher Schedule: ${CRON_SCHEDULE_MATCHER}"
    log "  llama-server URL: ${LLAMA_SERVER_URL:-http://localhost:8080}"
    log "  MCP Server Enabled: ${MCP_SERVER_ENABLED}"
    log "  MCP Server Port: ${MCP_SERVER_PORT}"
    log "  MCP Web Client Enabled: ${MCP_WEB_CLIENT_ENABLED}"
    log "  MCP Web Client Port: ${MCP_WEB_CLIENT_PORT}"
    echo ""
}

# Function to start MCP server
start_mcp_server() {
    if [ "$MCP_SERVER_ENABLED" != "true" ]; then
        log "${YELLOW}MCP Server: Disabled${NC}"
        return
    fi

    log "${GREEN}Starting MCP Server on port ${MCP_SERVER_PORT}...${NC}"
    cd /app
    uvicorn src.mcp_server.server:app \
        --host 0.0.0.0 \
        --port ${MCP_SERVER_PORT} \
        >> /var/log/job-search/mcp-server.log 2>&1 &

    MCP_SERVER_PID=$!
    echo $MCP_SERVER_PID > /var/run/mcp-server.pid

    # Wait a moment and check if it started
    sleep 2
    if kill -0 $MCP_SERVER_PID 2>/dev/null; then
        log "${GREEN}MCP Server started successfully (PID: $MCP_SERVER_PID)${NC}"
    else
        log "${RED}ERROR: MCP Server failed to start${NC}"
        log "${YELLOW}Check logs: /var/log/job-search/mcp-server.log${NC}"
    fi
}

# Function to start MCP web client
start_mcp_web_client() {
    if [ "$MCP_WEB_CLIENT_ENABLED" != "true" ]; then
        log "${YELLOW}MCP Web Client: Disabled${NC}"
        return
    fi

    log "${GREEN}Starting MCP Web Client on port ${MCP_WEB_CLIENT_PORT}...${NC}"
    cd /app
    python -m src.mcp_client.web.app \
        >> /var/log/job-search/mcp-web.log 2>&1 &

    MCP_WEB_PID=$!
    echo $MCP_WEB_PID > /var/run/mcp-web.pid

    # Wait a moment and check if it started
    sleep 2
    if kill -0 $MCP_WEB_PID 2>/dev/null; then
        log "${GREEN}MCP Web Client started successfully (PID: $MCP_WEB_PID)${NC}"
        log "${BLUE}Access web UI at: http://localhost:${MCP_WEB_CLIENT_PORT}${NC}"
    else
        log "${RED}ERROR: MCP Web Client failed to start${NC}"
        log "${YELLOW}Check logs: /var/log/job-search/mcp-web.log${NC}"
    fi
}

# Function to start cron mode
start_cron_mode() {
    log "${GREEN}Starting cron daemon...${NC}"

    # Create PID file for health check
    touch /var/run/crond.pid

    # Start cron in foreground
    service cron start

    log "${GREEN}Cron daemon started successfully${NC}"
    log "${BLUE}Container is running. Use 'docker logs -f' to view output${NC}"
    log "${BLUE}Log files:${NC}"
    log "  Scraper: /var/log/job-search/scraper.log"
    log "  Matcher: /var/log/job-search/matcher.log"
    log "  Cron: /var/log/cron.log"

    # Tail logs to keep container running and show output
    tail -f /var/log/cron.log /var/log/job-search/*.log 2>/dev/null &

    # Keep container running
    wait
}

# Function to start all services (MCP + Cron)
start_all_services() {
    log "${GREEN}Starting all services...${NC}"

    # Start MCP services
    start_mcp_server
    start_mcp_web_client

    # Setup and start cron if enabled
    if [ "$ENABLE_SCRAPER_CRON" = "true" ] || [ "$ENABLE_MATCHER_CRON" = "true" ]; then
        setup_cron

        # Create PID file for health check
        touch /var/run/crond.pid

        # Start cron in foreground
        service cron start
        log "${GREEN}Cron daemon started successfully${NC}"
    else
        log "${YELLOW}Cron jobs disabled${NC}"
    fi

    log "${BLUE}All services started. Log files:${NC}"
    [ "$MCP_SERVER_ENABLED" = "true" ] && log "  MCP Server: /var/log/job-search/mcp-server.log"
    [ "$MCP_WEB_CLIENT_ENABLED" = "true" ] && log "  MCP Web Client: /var/log/job-search/mcp-web.log"
    [ -f /var/run/crond.pid ] && log "  Scraper: /var/log/job-search/scraper.log"
    [ -f /var/run/crond.pid ] && log "  Matcher: /var/log/job-search/matcher.log"
    [ -f /var/run/crond.pid ] && log "  Cron: /var/log/cron.log"

    # Tail all logs
    tail -f /var/log/job-search/*.log /var/log/cron.log 2>/dev/null &

    # Keep container running
    wait
}

# Function to run manual command
run_manual_command() {
    log "${GREEN}Running manual command: $@${NC}"
    exec "$@"
}

# =============================================================================
# Main Execution
# =============================================================================

# Test configuration first
test_config

# Show current configuration
show_config

# Determine execution mode
case "${1:-all}" in
    all|mcp-all)
        # Default: Start all services (MCP + Cron)
        start_all_services
        ;;
    cron)
        # Cron jobs only (no MCP services)
        setup_cron
        start_cron_mode
        ;;
    mcp-server)
        # MCP server only
        start_mcp_server
        log "${BLUE}MCP Server running. Press Ctrl+C to stop.${NC}"
        tail -f /var/log/job-search/mcp-server.log
        ;;
    mcp-web)
        # MCP web client only
        start_mcp_web_client
        log "${BLUE}MCP Web Client running. Press Ctrl+C to stop.${NC}"
        tail -f /var/log/job-search/mcp-web.log
        ;;
    mcp)
        # Both MCP services (no cron)
        start_mcp_server
        start_mcp_web_client
        log "${BLUE}MCP services running. Press Ctrl+C to stop.${NC}"
        tail -f /var/log/job-search/mcp-server.log /var/log/job-search/mcp-web.log
        ;;
    scraper)
        log "${GREEN}Running job scraper manually...${NC}"
        log "Profile: ${ACTIVE_PROFILE}"
        cd /app
        exec python scripts/job_search.py --profile ${ACTIVE_PROFILE}
        ;;
    matcher)
        log "${GREEN}Running job matcher manually...${NC}"
        log "Profile: ${ACTIVE_PROFILE}"
        cd /app
        exec python scripts/job_matcher.py --profile ${ACTIVE_PROFILE} --input ${PROFILE_DIR}/data/jobs_latest.json --full-pipeline
        ;;
    cli)
        log "${GREEN}Running CLI command: ${@:2}${NC}"
        cd /app
        shift  # Remove 'cli' argument
        exec python -m src.cli.main "$@"
        ;;
    bash|sh)
        log "${GREEN}Starting interactive shell...${NC}"
        exec /bin/bash
        ;;
    *)
        run_manual_command "$@"
        ;;
esac
