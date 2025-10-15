#!/bin/bash
# =============================================================================
# Docker CLI Wrapper for Job Search Application
# =============================================================================
# This script provides easy access to the CLI from within the Docker container
#
# Usage:
#   cli [COMMAND] [OPTIONS]
#
# Examples:
#   cli stats
#   cli matcher report
#   cli tracker list --limit 50
#   cli system doctor
#
# This is equivalent to running:
#   python /app/cli.py [COMMAND] [OPTIONS]

set -e

# Change to app directory
cd /app

# Execute the CLI with all arguments
exec python -m src.cli.main "$@"
