"""Configuration management for 41Agent."""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """41Agent configuration loaded from environment variables."""

    # DashScope API
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")

    # VM Configuration
    vm_memory: str = os.getenv("VM_MEMORY", "4G")
    vm_cpus: int = int(os.getenv("VM_CPUS", "4"))
    vm_display_resolution: str = os.getenv("VM_DISPLAY_RESOLUTION", "1920x1080")
    vm_screenshot_fps: int = int(os.getenv("VM_SCREENSHOT_FPS", "30"))

    # QEMU Paths
    qemu_socket_path: str = os.getenv("QEMU_SOCKET_PATH", "/tmp/qemu-qmp.sock")
    qemu_vnc_display: str = os.getenv("QEMU_VNC_DISPLAY", ":0")

    # Inochi2d Configuration
    inochi2d_vmc_host: str = os.getenv("INOCHI2D_VMC_HOST", "127.0.0.1")
    inochi2d_vmc_port: int = int(os.getenv("INOCHI2D_VMC_PORT", "39540"))
    inochi2d_avatar_path: str = os.getenv("INOCHI2D_AVATAR_PATH", "assets/avatar.inx")

    # Memory Configuration
    chroma_db_path: str = os.getenv("CHROMA_DB_PATH", "db/chromadb")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # Audio Configuration
    audio_sample_rate: int = int(os.getenv("AUDIO_SAMPLE_RATE", "24000"))
    audio_voice: str = os.getenv("AUDIO_VOICE", "Cherry")

    # UI Configuration
    ui_width: int = int(os.getenv("UI_WIDTH", "1920"))
    ui_height: int = int(os.getenv("UI_HEIGHT", "1080"))
    avatar_width: int = int(os.getenv("AVATAR_WIDTH", "400"))
    avatar_height: int = int(os.getenv("AVATAR_HEIGHT", "600"))

    # Derived properties
    @property
    def vm_width(self) -> int:
        return int(self.vm_display_resolution.split("x")[0])

    @property
    def vm_height(self) -> int:
        return int(self.vm_display_resolution.split("x")[1])

    @property
    def avatar_position_x(self) -> int:
        return self.ui_width - self.avatar_width - 50

    @property
    def avatar_position_y(self) -> int:
        return self.ui_height - self.avatar_height - 50

    def validate(self) -> bool:
        """Validate required configuration."""
        if not self.dashscope_api_key:
            raise ValueError("DASHSCOPE_API_KEY is required")
        return True


# Global config instance
config = Config()
