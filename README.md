# 41Agent - Omnimodal Autonomous AI Agent

41Agent is an advanced omnimodal autonomous AI agent featuring:

## Features

1. **Omnimodal Interaction** - Real-time video/audio input and audio output using qwen3-omni-flash
2. **Autonomous Behavior** - Agent41 can act independently without user commands
3. **Unlimited Memory** - RAG-based persistent memory system
4. **VM Control** - Full QEMU VM manipulation
5. **Inochi2d Avatar** - Live avatar rendering in bottom-right corner

## Requirements

- Python 3.11+
- QEMU (for VM functionality)
- Inochi2d Session (for avatar)
- ffmpeg (for audio/video processing)
- DashScope API key (for qwen3-omni-flash)

## Installation

```bash
# Install uv if not already installed
curl -sSf https://uv.run | sh

# Install dependencies
uv sync
```

## Usage

1. Prepare your files:
   - Inochi2d avatar file (`.inx`) in `assets/avatar.inx`
   - VM ISO/disk image in `assets/vm.iso`

2. Set environment variables:
   ```bash
   export DASHSCOPE_API_KEY="your-api-key"
   ```

3. Run the agent:
   ```bash
   uv run python run.py
   ```

## Controls

- **T**: Open chat input
- **Esc**: Close chat / Exit
- **Ctrl+C**: Emergency stop

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    41Agent Core                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │   Agent41   │  │   Memory    │  │   Behavior      │  │
│  │   (Omni)    │  │   (RAG)     │  │   Engine        │  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────┘  │
│         │                │                               │
│         └────────────────┴────────────────┐              │
│                                            ▼              │
│  ┌──────────────────────────────────────────────────┐    │
│  │              Orchestration Layer                  │    │
│  └─────────────────────┬────────────────────────────┘    │
│                        │                                  │
│         ┌──────────────┼──────────────┐                  │
│         ▼              ▼              ▼                  │
│  ┌───────────┐  ┌───────────┐  ┌─────────────────┐       │
│  │ Qwen3-    │  │   VM      │  │   Inochi2d      │       │
│  │ Omni-Flash│  │ Controller│  │   Controller    │       │
│  └───────────┘  └───────────┘  └─────────────────┘       │
└─────────────────────────────────────────────────────────┘
```
