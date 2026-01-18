"""QEMU VM controller for 41Agent."""

import asyncio
import os
import time
import base64
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from .config import config


class VMState(Enum):
    """VM state enumeration."""

    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class VMScreenshot:
    """VM screenshot data."""

    data: bytes
    width: int
    height: int
    timestamp: float


class VMController:
    """Controller for QEMU VM via QMP and VNC."""

    def __init__(self):
        self.state = VMState.STOPPED
        self.qmp_socket = config.qemu_socket_path
        self.vnc_display = config.qemu_vnc_display
        self._qmp_client = None
        self._vnc_client = None

    async def connect(self) -> bool:
        """Connect to QEMU VM.

        Returns:
            True if connected successfully
        """
        try:
            # Import QMP client
            try:
                from qemu.qmp import QMPClient

                self._qmp_client = QMPClient("agent41-vm")
                await self._qmp_client.connect(self.qmp_socket)
                self.state = VMState.RUNNING
                return True
            except ImportError:
                # Fallback:MP not Q available, use vncdotool
                from vncdotool import api

                self._vnc_client = api.connect(f"localhost{self.vnc_display}")
                self.state = VMState.RUNNING
                return True

        except Exception as e:
            print(f"Failed to connect to VM: {e}")
            self.state = VMState.ERROR
            return False

    async def disconnect(self):
        """Disconnect from VM."""
        if self._qmp_client:
            await self._qmp_client.disconnect()
            self._qmp_client = None

        if self._vnc_client:
            self._vnc_client.disconnect()
            self._vnc_client = None

        self.state = VMState.STOPPED

    async def get_screenshot(self) -> Optional[VMScreenshot]:
        """Capture VM screen.

        Returns:
            VMScreenshot or None if failed
        """
        try:
            if self._qmp_client:
                # Use QMP screendump
                screenshot_path = f"/tmp/vm_screenshot_{int(time.time())}.png"

                await self._qmp_client.execute(
                    "screendump", {"filename": screenshot_path, "format": "png"}
                )

                # Wait for file to be written
                await asyncio.sleep(0.5)

                if Path(screenshot_path).exists():
                    with open(screenshot_path, "rb") as f:
                        data = f.read()
                    os.remove(screenshot_path)

                    return VMScreenshot(
                        data=data,
                        width=config.vm_width,
                        height=config.vm_height,
                        timestamp=time.time(),
                    )

            elif self._vnc_client:
                # Use vncdotool
                from PIL import Image
                import io

                self._vnc_client.captureScreen("/tmp/vm_screenshot.png")
                with open("/tmp/vm_screenshot.png", "rb") as f:
                    data = f.read()

                return VMScreenshot(
                    data=data,
                    width=config.vm_width,
                    height=config.vm_height,
                    timestamp=time.time(),
                )

        except Exception as e:
            print(f"Failed to capture screenshot: {e}")

        return None

    async def click(self, x: int, y: int, button: str = "left"):
        """Click at position.

        Args:
            x: X coordinate (0 to width-1)
            y: Y coordinate (0 to height-1)
            button: Mouse button (left, middle, right)
        """
        if self._qmp_client:
            # Convert to QEMU coordinates (0-32767)
            qx = int((x / config.vm_width) * 32767)
            qy = int((y / config.vm_height) * 32767)

            await self._qmp_client.execute(
                "input-send-event",
                {
                    "events": [
                        {"type": "abs", "data": {"axis": "x", "value": qx}},
                        {"type": "abs", "data": {"axis": "y", "value": qy}},
                        {"type": "btn", "data": {"down": True, "button": button}},
                    ]
                },
            )

            await self._qmp_client.execute(
                "input-send-event",
                {
                    "events": [
                        {"type": "btn", "data": {"down": False, "button": button}}
                    ]
                },
            )

        elif self._vnc_client:
            self._vnc_client.mouseClick(x, y)

    async def double_click(self, x: int, y: int, button: str = "left"):
        """Double click at position."""
        await self.click(x, y, button)
        await asyncio.sleep(0.1)
        await self.click(x, y, button)

    async def type_text(self, text: str):
        """Type text into VM.

        Args:
            text: Text to type
        """
        if self._qmp_client:
            for char in text:
                await self._send_key(char)
                await asyncio.sleep(0.01)

        elif self._vnc_client:
            self._vnc_client.keyPress(text)

    async def _send_key(self, char: str):
        """Send a single key.

        Args:
            char: Character to send
        """
        # Map character to QEMU key code
        key_map = {
            "a": "a",
            "b": "b",
            "c": "c",
            "d": "d",
            "e": "e",
            "f": "f",
            "g": "g",
            "h": "h",
            "i": "i",
            "j": "j",
            "k": "k",
            "l": "l",
            "m": "m",
            "n": "n",
            "o": "o",
            "p": "p",
            "q": "q",
            "r": "r",
            "s": "s",
            "t": "t",
            "u": "u",
            "v": "v",
            "w": "w",
            "x": "x",
            "y": "y",
            "z": "z",
            "0": "0",
            "1": "1",
            "2": "2",
            "3": "3",
            "4": "4",
            "5": "5",
            "6": "6",
            "7": "7",
            "8": "8",
            "9": "9",
            " ": "spc",
            "\n": "ret",
            "\t": "tab",
            "!": "shift-1",
            "@": "shift-2",
            "#": "shift-3",
            "$": "shift-4",
            "%": "shift-5",
            "^": "shift-6",
            "&": "shift-7",
            "*": "shift-8",
            "(": "shift-9",
            ")": "shift-0",
            "-": "minus",
            "_": "shift-minus",
            "=": "equal",
            "+": "shift-equal",
            "[": "bracket_left",
            "]": "bracket_right",
            "{": "shift-bracket_left",
            "}": "shift-bracket_right",
            "\\": "backslash",
            "|": "shift-backslash",
            ";": "semicolon",
            ":": "shift-semicolon",
            "'": "apostrophe",
            '"': "shift-apostrophe",
            ",": "comma",
            "<": "shift-comma",
            ".": "dot",
            ">": "shift-dot",
            "/": "slash",
            "?": "shift-slash",
        }

        key = key_map.get(char.lower(), char)

        if "-" in key:
            # Handle modifier combinations
            parts = key.split("-")
            for part in parts:
                await self._qmp_client.execute(
                    "input-send-event",
                    {
                        "events": [
                            {
                                "type": "key",
                                "data": {
                                    "down": True,
                                    "key": {"type": "qcode", "data": part},
                                },
                            }
                        ]
                    },
                )
            for part in reversed(parts):
                await self._qmp_client.execute(
                    "input-send-event",
                    {
                        "events": [
                            {
                                "type": "key",
                                "data": {
                                    "down": False,
                                    "key": {"type": "qcode", "data": part},
                                },
                            }
                        ]
                    },
                )
        else:
            await self._qmp_client.execute(
                "input-send-event",
                {
                    "events": [
                        {
                            "type": "key",
                            "data": {
                                "down": True,
                                "key": {"type": "qcode", "data": key},
                            },
                        },
                    ]
                },
            )
            await self._qmp_client.execute(
                "input-send-event",
                {
                    "events": [
                        {
                            "type": "key",
                            "data": {
                                "down": False,
                                "key": {"type": "qcode", "data": key},
                            },
                        },
                    ]
                },
            )

    async def press_key(self, key: str):
        """Press a key.

        Args:
            key: Key name (e.g., 'ctrl', 'alt', 'delete', 'f1')
        """
        if self._qmp_client:
            await self._qmp_client.execute(
                "input-send-event",
                {
                    "events": [
                        {
                            "type": "key",
                            "data": {
                                "down": True,
                                "key": {"type": "qcode", "data": key},
                            },
                        },
                    ]
                },
            )
            await self._qmp_client.execute(
                "input-send-event",
                {
                    "events": [
                        {
                            "type": "key",
                            "data": {
                                "down": False,
                                "key": {"type": "qcode", "data": key},
                            },
                        },
                    ]
                },
            )

        elif self._vnc_client:
            self._vnc_client.keyPress(key)

    async def move_mouse(self, x: int, y: int):
        """Move mouse to position.

        Args:
            x: X coordinate
            y: Y coordinate
        """
        if self._qmp_client:
            qx = int((x / config.vm_width) * 32767)
            qy = int((y / config.vm_height) * 32767)

            await self._qmp_client.execute(
                "input-send-event",
                {
                    "events": [
                        {"type": "abs", "data": {"axis": "x", "value": qx}},
                        {"type": "abs", "data": {"axis": "y", "value": qy}},
                    ]
                },
            )

        elif self._vnc_client:
            self._vnc_client.mouseMove(x, y)

    async def drag(self, x1: int, y1: int, x2: int, y2: int, button: str = "left"):
        """Drag from one position to another.

        Args:
            x1: Start X
            y1: Start Y
            x2: End X
            y2: End Y
            button: Mouse button
        """
        await self.click(x1, y1, button)
        await self.move_mouse(x2, y2)
        await self.click(x2, y2, button)

    async def get_status(self) -> Dict[str, Any]:
        """Get VM status.

        Returns:
            Status dict
        """
        if self._qmp_client:
            try:
                status = await self._qmp_client.execute("query-status")
                return {
                    "running": status.get("running", False),
                    "singlestep": status.get("singlestep", False),
                    "status": status.get("status", "unknown"),
                }
            except Exception:
                pass

        return {
            "running": self.state == VMState.RUNNING,
            "singlestep": False,
            "status": self.state.value,
        }

    async def pause(self):
        """Pause VM."""
        if self._qmp_client:
            await self._qmp_client.execute("stop")
        self.state = VMState.PAUSED

    async def resume(self):
        """Resume VM."""
        if self._qmp_client:
            await self._qmp_client.execute("cont")
        self.state = VMState.RUNNING

    async def shutdown(self):
        """Graceful shutdown VM."""
        if self._qmp_client:
            await self._qmp_client.execute("system_powerdown")
        self.state = VMState.STOPPED

    async def reset(self):
        """Reset VM."""
        if self._qmp_client:
            await self._qmp_client.execute("system_reset")
        self.state = VMState.RUNNING


class QEMULauncher:
    """Helper to launch QEMU VM."""

    @staticmethod
    def get_command(
        disk_path: str,
        iso_path: Optional[str] = None,
        memory: str = "4G",
        cpus: int = 4,
        socket_path: str = "/tmp/qemu-qmp.sock",
        vnc_display: str = ":0",
    ) -> str:
        """Get QEMU launch command.

        Args:
            disk_path: Path to disk image
            iso_path: Optional ISO to boot from
            memory: Memory allocation
            cpus: Number of CPUs
            socket_path: QMP socket path
            vnc_display: VNC display

        Returns:
            QEMU command string
        """
        cmd = [
            "qemu-system-x86_64",
            "-enable-kvm",
            f"-cpu host",
            f"-m {memory}",
            f"-smp {cpus}",
            "-display none",
            f"-vnc {vnc_display}",
            "-vga qxl",
            f"-qmp unix:{socket_path},server,wait=off",
            f"-drive file={disk_path},format=qcow2,if=virtio",
        ]

        if iso_path:
            cmd.append(f"-cdrom {iso_path}")

        cmd.append("-netdev user,id=net0,hostfwd=tcp::2222-:22")
        cmd.append("-device virtio-net-pci,netdev=net0")

        return " ".join(cmd)

    @staticmethod
    def launch(
        disk_path: str,
        iso_path: Optional[str] = None,
        memory: str = "4G",
        cpus: int = 4,
        socket_path: str = "/tmp/qemu-qmp.sock",
        vnc_display: str = ":0",
    ) -> bool:
        """Launch QEMU VM.

        Args:
            disk_path: Path to disk image
            iso_path: Optional ISO to boot from
            memory: Memory allocation
            cpus: Number of CPUs
            socket_path: QMP socket path
            vnc_display: VNC display

        Returns:
            True if launched successfully
        """
        import subprocess

        cmd = QEMULauncher.get_command(
            disk_path, iso_path, memory, cpus, socket_path, vnc_display
        )

        try:
            subprocess.Popen(
                cmd.split(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as e:
            print(f"Failed to launch QEMU: {e}")
            return False
