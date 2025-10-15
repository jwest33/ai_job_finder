#!/usr/bin/env python3
"""
CLI Entry Point Wrapper

Convenience wrapper for the main CLI module.
Usage: python cli.py [COMMAND] [OPTIONS]
"""

if __name__ == "__main__":
    from src.cli.main import main
    main()
