#!/usr/bin/env python3
"""
Email Setup Wrapper - Launches the actual email setup script

This wrapper exists to maintain CLI compatibility with:
    python cli.py email setup
"""

import sys
from pathlib import Path

# Import and run the actual setup script
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.email_setup import main

if __name__ == "__main__":
    main()
