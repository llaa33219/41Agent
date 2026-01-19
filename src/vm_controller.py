"""QEMU VM controller for 41Agent."""

import asyncio
import json
import socket
import time
from pathlib import Path
from typing import Optional, Dict, Any
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


class QMPClient:
    """Simple QEMU QMP client using raw sockets."""

    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.socket = None
        self._connected = False

    async def connect(self) -> bool:
        """Connect to QMP socket."""
        try:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect(self.socket_path)

            # Read greeting
            greeting = self.socket.recv(4096)
            print(f"QMP greeting: {greeting[:200]}")

            # Send QMP-capability command
            await self.execute("qmp_capabilities")

            self._connected = True
            return True
        except Exception as e:
            print(f"Failed to connect to QMP: {e}")
            self._connected = False
            return False

    async def execute(
        self, command: str, args: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Execute a QMP command."""
        if not self._connected:
            return None

        msg = {"execute": command}
        if args:
            msg["arguments"] = args

        try:
            self.socket.sendall((json.dumps(msg) + "\n").encode())

            # Read response
            response = b""
            while True:
                chunk = self.socket.recv(4096)
                response += chunk
                if b"\n" in response:
                    break

            result = json.loads(response.decode())
            return result
        except Exception as e:
            print(f"QMP command failed: {e}")
            return None

    def disconnect(self):
        """Disconnect from QMP."""
        if self.socket:
            self.socket.close()
            self.socket = None
        self._connected = False


class VMController:
    """Controller for QEMU VM via QMP and VNC."""

    def __init__(self):
        self.state = VMState.STOPPED
        self.qmp_socket = config.qemu_socket_path
        self.vnc_display = config.qemu_vnc_display
        self._qmp_client: Optional[QMPClient] = None
        self._vnc_client = None

    async def connect(self) -> bool:
        """Connect to QEMU VM.

        Returns:
            True if connected successfully
        """
        try:
            # Try QMP connection first
            self._qmp_client = QMPClient(self.qmp_socket)
            connected = await self._qmp_client.connect()

            if connected:
                self.state = VMState.RUNNING
                print("Connected to QEMU via QMP")
                return True

        except Exception as e:
            print(f"QMP connection failed: {e}")

        # Fallback: try vncdotool
        try:
            from vncdotool import api

            self._vnc_client = api.connect(f"localhost{self.vnc_display}")
            self.state = VMState.RUNNING
            print("Connected to QEMU via VNC")
            return True
        except Exception as e:
            print(f"VNC connection failed: {e}")
            self.state = VMState.ERROR
            return False

    async def disconnect(self):
        """Disconnect from VM."""
        if self._qmp_client:
            self._qmp_client.disconnect()
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

                result = await self._qmp_client.execute(
                    "screendump", {"filename": screenshot_path, "format": "png"}
                )

                # Wait for file
                await asyncio.sleep(0.5)

                if Path(screenshot_path).exists():
                    with open(screenshot_path, "rb") as f:
                        data = f.read()
                    return VMScreenshot(
                        data=data,
                        width=config.vm_width,
                        height=config.vm_height,
                        timestamp=time.time(),
                    )

            elif self._vnc_client:
                # Use vncdotool
                screenshot_path = f"/tmp/vm_screenshot_{int(time.time())}.png"
                self._vnc_client.captureScreen(screenshot_path)

                await asyncio.sleep(0.3)

                if Path(screenshot_path).exists():
                    with open(screenshot_path, "rb") as f:
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

            await asyncio.sleep(0.05)

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
        for char in text:
            await self._send_key(char)
            await asyncio.sleep(0.02)

    async def _send_key(self, char: str):
        """Send a single key."""
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
        }

        key = key_map.get(char.lower(), char)

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
            await asyncio.sleep(0.02)
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

    async def press_key(self, key: str):
        """Press a key.

        Args:
            key: Key name (e.g., 'ctrl', 'alt', 'delete')
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
            await asyncio.sleep(0.05)
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
        """Move mouse to position."""
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

    async def get_status(self) -> Dict[str, Any]:
        """Get VM status."""
        if self._qmp_client:
            result = await self._qmp_client.execute("query-status")
            if result:
                return {
                    "running": result.get("running", False),
                    "status": result.get("status", "unknown"),
                }

        return {
            "running": self.state == VMState.RUNNING,
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
        """Get QEMU launch command."""
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
        """Launch QEMU VM."""
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
