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
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.orchestrator import main


if __name__ == "__main__":
    try:
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
        print("Starting 41Agent...")
        print("=" * 60)

        asyncio.run(main())

    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
