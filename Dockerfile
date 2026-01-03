# =============================================================================
# AI Job Finder - Multi-stage Dockerfile
# =============================================================================

# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/web

# Install dependencies
COPY web/package*.json ./
RUN npm ci --silent

# Copy source and build
COPY web/ ./
RUN npm run build

# =============================================================================
# Stage 2: Python runtime
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    # Required for Playwright
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser with all system dependencies
RUN playwright install chromium && playwright install-deps chromium

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/web/dist ./web/dist

# Create directory for profile data mount
RUN mkdir -p profiles

# Set Python path
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose API port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Default command: start FastAPI backend (serves frontend from web/dist)
CMD ["python", "-m", "src.mcp_server.server"]
