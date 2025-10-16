# =============================================================================
# Job Search & Matcher - Docker Image
# =============================================================================
# Multi-stage build for optimized image size
# Supports automated job scraping and AI-powered matching with cron scheduling

FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Set work directory
WORKDIR /app

# Install system dependencies including Playwright requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    curl \
    # Playwright/Chromium dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# Stage 2: Dependencies
# =============================================================================
FROM base AS dependencies

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    playwright install chromium && \
    playwright install-deps chromium

# =============================================================================
# Stage 3: Application
# =============================================================================
FROM base AS application

# Copy Python packages from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy Playwright browsers from dependencies stage
COPY --from=dependencies /root/.cache/ms-playwright /root/.cache/ms-playwright

# Copy application code
COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY requirements.txt /app/

# Create necessary directories
RUN mkdir -p /app/data \
    /app/reports \
    /app/templates \
    /app/credentials \
    /app/logs \
    /var/log/job-search \
    /app/conversations/active \
    /app/conversations/archives \
    /app/conversations/data

# Copy entrypoint and CLI wrapper scripts
COPY docker/entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY docker/cli.sh /usr/local/bin/cli

# Convert line endings to Unix format (in case they were saved with Windows CRLF)
# and make scripts executable
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh && \
    sed -i 's/\r$//' /usr/local/bin/cli && \
    chmod +x /usr/local/bin/docker-entrypoint.sh && \
    chmod +x /usr/local/bin/cli

# Create cron log file
RUN touch /var/log/cron.log

# Health check (checks cron, MCP server, and web client if enabled)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD (test -f /var/run/crond.pid || exit 0) && \
        (test "$MCP_SERVER_ENABLED" != "true" || curl -f http://0.0.0.0:${MCP_SERVER_PORT:-3000}/health || exit 1) && \
        (test "$MCP_WEB_CLIENT_ENABLED" != "true" || curl -f http://0.0.0.0:${MCP_WEB_CLIENT_PORT:-5000}/api/health || exit 1)

# Set entrypoint
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default command (can be overridden)
CMD ["all"]

# Labels
LABEL maintainer="Job Search Project" \
      description="Automated job scraping and AI-powered matching system" \
      version="1.0"
