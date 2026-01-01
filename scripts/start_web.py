#!/usr/bin/env python3
"""
Start Web Application

Launches both the backend API server and frontend dev server.
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
WEB_DIR = PROJECT_ROOT / "web"
BACKEND_PORT = 3000
FRONTEND_PORT = 5173

# Track child processes for cleanup
processes = []


def check_node_installed():
    """Check if Node.js is installed."""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            shell=True
        )
        return result.returncode == 0
    except Exception:
        return False


def check_npm_installed():
    """Check if npm is installed."""
    try:
        result = subprocess.run(
            ["npm", "--version"],
            capture_output=True,
            text=True,
            shell=True
        )
        return result.returncode == 0
    except Exception:
        return False


def install_frontend_deps():
    """Install frontend dependencies if node_modules doesn't exist."""
    node_modules = WEB_DIR / "node_modules"

    if not node_modules.exists():
        print("\n[Frontend] Installing dependencies...")
        result = subprocess.run(
            ["npm", "install"],
            cwd=str(WEB_DIR),
            shell=True
        )
        if result.returncode != 0:
            print("[Frontend] Failed to install dependencies")
            return False
        print("[Frontend] Dependencies installed successfully")

    return True


def start_backend():
    """Start the FastAPI backend server."""
    print(f"\n[Backend] Starting on http://localhost:{BACKEND_PORT}")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    process = subprocess.Popen(
        [sys.executable, "-m", "src.mcp_server.server"],
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    processes.append(("Backend", process))
    return process


def start_frontend():
    """Start the Vite frontend dev server."""
    print(f"\n[Frontend] Starting on http://localhost:{FRONTEND_PORT}")

    process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(WEB_DIR),
        shell=True,
    )
    processes.append(("Frontend", process))
    return process


def cleanup(signum=None, frame=None):
    """Clean up child processes."""
    print("\n\nShutting down...")

    for name, process in processes:
        if process.poll() is None:
            print(f"[{name}] Stopping...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    print("Goodbye!")
    sys.exit(0)


def main():
    """Main entry point."""
    print("=" * 50)
    print("  AI Job Finder - Web Application")
    print("=" * 50)

    # Check prerequisites
    if not check_node_installed():
        print("\n[Error] Node.js is not installed.")
        print("Please install Node.js from https://nodejs.org/")
        sys.exit(1)

    if not check_npm_installed():
        print("\n[Error] npm is not installed.")
        print("Please install Node.js from https://nodejs.org/")
        sys.exit(1)

    # Check if web directory exists
    if not WEB_DIR.exists():
        print(f"\n[Error] Web directory not found: {WEB_DIR}")
        sys.exit(1)

    # Install frontend dependencies
    if not install_frontend_deps():
        sys.exit(1)

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Start services
    backend = start_backend()
    time.sleep(2)  # Give backend time to start

    frontend = start_frontend()
    time.sleep(2)  # Give frontend time to start

    print("\n" + "=" * 50)
    print("  Services started successfully!")
    print("=" * 50)
    print(f"\n  Backend API:  http://localhost:{BACKEND_PORT}")
    print(f"  Frontend UI:  http://localhost:{FRONTEND_PORT}")
    print("\n  Press Ctrl+C to stop all services")
    print("=" * 50 + "\n")

    # Wait for processes
    try:
        while True:
            # Check if any process has died
            for name, process in processes:
                if process.poll() is not None:
                    print(f"\n[{name}] Process exited with code {process.returncode}")
                    cleanup()
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
