#!/usr/bin/env python3
"""
41Agent - Omnimodal Autonomous AI Agent

Usage:
    python run.py [--help] [--headless]
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
    """Ensure all dependencies are installed with uv."""
    project_root = Path(__file__).parent
    pyproject_path = project_root / "pyproject.toml"

    if not pyproject_path.exists():
        print("Error: pyproject.toml not found!")
        sys.exit(1)

    if not check_uv_installed():
        print("Installing uv...")
        if not install_uv():
            print("Failed to install uv.")
            sys.exit(1)

    # Add uv to PATH if needed
    uv_home = Path.home() / ".local" / "bin"
    uv_path = uv_home / "uv"
    if uv_path.exists() and str(uv_home) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(uv_home) + os.pathsep + os.environ.get("PATH", "")

    # Check if .venv already exists
    venv_python = project_root / ".venv" / "bin" / "python"

    if venv_python.exists():
        # Check if pygame is installed
        result = subprocess.run(
            [str(venv_python), "-c", "import pygame"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print("Dependencies already installed.")
            return str(venv_python)
        else:
            print("Updating dependencies...")
    else:
        print("Creating virtual environment and installing dependencies...")

    result = subprocess.run(
        ["uv", "sync"],
        cwd=project_root,
        capture_output=True,
        text=True,
        env={**os.environ, "UV_NO_WRAP": "1"},
        timeout=600,
    )

    if result.returncode != 0:
        print(f"Failed to install dependencies:")
        print(result.stderr)
        sys.exit(1)

    print("Dependencies installed successfully!")
    return str(venv_python)


def main_entry():
    """Main entry point."""
    print("=" * 60)
    print("41Agent - Omnimodal Autonomous AI Agent")
    print("=" * 60)
    print()
    print("Controls:")
    print("  T     - Toggle chat mode (GUI only)")
    print("  ESC   - Close chat / Exit")
    print("  Ctrl+C - Emergency stop")
    print()
    print("Options:")
    print("  --headless    Run without GUI display")
    print("  --help        Show this message")
    print()

    # Check for help flag
    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h"]:
        print("Usage: python run.py [--headless]")
        print()
        print("This script will automatically:")
        print("  1. Install uv if not present")
        print("  2. Install all dependencies")
        print("  3. Run 41Agent")
        print()
        print("Requirements:")
        print("  - DASHSCOPE_API_KEY environment variable")
        print("  - For VM: QEMU installed, disk image in assets/vm.qcow2")
        print("  - For avatar: Inochi2d Session, avatar in assets/avatar.inx")
        sys.exit(0)

    # Check for headless mode
    headless = "--headless" in sys.argv or os.getenv("HEADLESS", "").lower() == "true"

    # Set headless mode
    if headless:
        os.environ["HEADLESS"] = "true"

    # Check if running from venv python
    venv_python = Path("/home/luke/41Agent/.venv/bin/python")
    current_python = Path(sys.executable)
    is_from_venv = venv_python.exists() and str(current_python) == str(venv_python)

    # Check API key
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("DASHSCOPE_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    os.environ["DASHSCOPE_API_KEY"] = api_key
                    break

    if not api_key:
        print("Error: DASHSCOPE_API_KEY not set!")
        print("Please set it before continuing:")
        print("  export DASHSCOPE_API_KEY='your-api-key'")
        print("Or create a .env file with:")
        print("  DASHSCOPE_API_KEY=your-api-key")
        sys.exit(1)

    # Set headless mode
    if headless:
        os.environ["HEADLESS"] = "true"

    print("Initializing 41Agent...")
    print("=" * 60)

    # Ensure dependencies
    if not is_from_venv:
        venv_python = ensure_dependencies()
        # Run with venv python
        new_env = {**os.environ, "HEADLESS": "true" if headless else "false"}
        os.execve(
            venv_python, [venv_python, str(Path(__file__))] + sys.argv[1:], new_env
        )

    # Run the agent (only reached if already in venv)
    try:
        from src.orchestrator import main

        asyncio.run(main())
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
