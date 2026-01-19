#!/usr/bin/env python3
"""
41Agent - Omnimodal Autonomous AI Agent

Usage:
    python run.py [--help]

Requirements:
    - QEMU installed (for VM functionality)
    - Inochi2d Session running (for avatar)
    - DashScope API key (set DASHSCOPE_API_KEY environment variable)

Controls:
    T - Toggle chat mode
    ESC - Close chat / Exit
    Ctrl+C - Emergency stop
"""

import asyncio
import sys
import subprocess
import os
from pathlib import Path


def check_uv_installed():
    """Check if uv is installed."""
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_uv():
    """Install uv using the official installer."""
    print("Installing uv...")
    try:
        result = subprocess.run(
            ["curl", "-sSf", "https://uv.run", "|", "sh"],
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            print(f"Failed to install uv: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Failed to install uv: {e}")
        return False


def ensure_dependencies():
    """Ensure all dependencies are installed using uv."""
    project_root = Path(__file__).parent

    # Check if pyproject.toml exists
    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.exists():
        print("Error: pyproject.toml not found!")
        sys.exit(1)

    # Check if uv is installed
    if not check_uv_installed():
        print("uv not found. Installing uv...")
        if not install_uv():
            print("Failed to install uv. Please install manually:")
            print("  curl -sSf https://uv.run | sh")
            sys.exit(1)

    # Add uv to PATH if it was just installed
    uv_home = Path.home() / ".local" / "bin"
    uv_path = uv_home / "uv"
    if uv_path.exists() and str(uv_home) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(uv_home) + os.pathsep + os.environ.get("PATH", "")

    # Run uv sync to install dependencies
    print("Installing dependencies with uv...")
    result = subprocess.run(
        ["uv", "sync"], cwd=project_root, capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"Failed to install dependencies: {result.stderr}")
        sys.exit(1)

    print("Dependencies installed successfully!")
    return True


def run_agent():
    """Run the main 41Agent application."""
    # Add src to path
    project_root = Path(__file__).parent
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # Run the main application
    from src.orchestrator import main

    asyncio.run(main())


def main_entry():
    """Main entry point that handles all setup."""
    print("=" * 60)
    print("41Agent - Omnimodal Autonomous AI Agent")
    print("=" * 60)
    print()
    print("Controls:")
    print("  T     - Toggle chat mode")
    print("  ESC   - Close chat / Exit")
    print("  Ctrl+C - Emergency stop")
    print()
    print("Requirements:")
    print("  - QEMU installed")
    print("  - Inochi2d Session running on port 39540")
    print("  - DASHSCOPE_API_KEY environment variable set")
    print()

    # Check for --help flag
    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h"]:
        print("Usage: python run.py")
        print()
        print("This script will automatically:")
        print("  1. Install uv if not present")
        print("  2. Install all dependencies")
        print("  3. Run 41Agent")
        print()
        print("Make sure to set DASHSCOPE_API_KEY before running!")
        sys.exit(0)

    # Check if DASHSCOPE_API_KEY is set
    api_key = os.getenv("DASHSCOPE_API_KEY")

    # Also check .env file if not in environment
    if not api_key:
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("DASHSCOPE_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    os.environ["DASHSCOPE_API_KEY"] = api_key
                    break

    if not api_key:
        print("Warning: DASHSCOPE_API_KEY not set!")
        print("Please set it before continuing:")
        print("  export DASHSCOPE_API_KEY='your-api-key'")
        print()
        print("Or create a .env file with:")
        print("  DASHSCOPE_API_KEY=your-api-key")
        print()
        response = input("Continue anyway? (y/n): ").strip().lower()
        if response != "y":
            print("Exiting...")
            sys.exit(0)

    print("Initializing 41Agent...")
    print("=" * 60)

    # Ensure dependencies are installed
    ensure_dependencies()

    # Run the agent
    try:
        run_agent()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main_entry()
