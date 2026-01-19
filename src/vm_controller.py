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


class VMController:
    """Controller for QEMU VM via QMP and VNC."""

    def __init__(self):
        self.state = VMState.STOPPED
        self.qmp_socket = config.qemu_socket_path
        self.vnc_display = config.qemu_vnc_display
        self._connected = False

    async def connect(self) -> bool:
        """Connect to QEMU VM.

        Returns:
            True if connected successfully
        """
        # Try QMP connection (non-blocking with short timeout)
        loop = asyncio.get_running_loop()

        def try_connect():
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                sock.connect(self.qmp_socket)
                sock.close()
                return True
            except (socket.timeout, ConnectionRefusedError, FileNotFoundError):
                return False
            except Exception:
                return False

        try:
            connected = await asyncio.wait_for(
                loop.run_in_executor(None, try_connect), timeout=2.0
            )
            if connected:
                self._connected = True
                self.state = VMState.RUNNING
                print("Connected to VM (QMP)")
                return True
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            pass  # Silently continue to next option

        # Try VNC connection
        def try_vnc():
            import socket as sock

            try:
                vnc_port = 5900 + int(
                    self.vnc_display.replace(":", "")
                    .replace(":0", "0")
                    .replace(":1", "1")
                )
                s = sock.socket(sock.AF_INET, sock.SOCK_STREAM)
                s.settimeout(1.0)
                s.connect(("127.0.0.1", vnc_port))
                s.close()
                return True
            except Exception:
                return False

        try:
            connected = await asyncio.wait_for(
                loop.run_in_executor(None, try_vnc), timeout=2.0
            )
            if connected:
                self._connected = True
                self.state = VMState.RUNNING
                print("Connected to VM (VNC)")
                return True
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            pass

        # No VM available
        print("VM not running (will run in observation mode)")
        self.state = VMState.STOPPED
        self._connected = False
        return False

    async def disconnect(self):
        """Disconnect from VM."""
        self._connected = False
        self.state = VMState.STOPPED

    async def get_screenshot(self) -> Optional[VMScreenshot]:
        """Capture VM screen.

        Returns:
            VMScreenshot or None if failed
        """
        if not self._connected:
            return None

        # Try QMP screendump
        def try_screenshot():
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect(self.qmp_socket)

                # Read greeting
                sock.recv(4096)

                # Send screendump command
                screenshot_path = f"/tmp/vm_screenshot_{int(time.time())}.png"
                msg = (
                    json.dumps(
                        {
                            "execute": "screendump",
                            "arguments": {"filename": screenshot_path},
                        }
                    )
                    + "\n"
                )
                sock.sendall(msg.encode())

                # Wait for file
                time.sleep(0.3)

                if Path(screenshot_path).exists():
                    with open(screenshot_path, "rb") as f:
                        data = f.read()
                    Path(screenshot_path).unlink()
                    return data

                sock.close()
            except Exception:
                pass
            return None

        loop = asyncio.get_running_loop()
        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(None, try_screenshot), timeout=5.0
            )
            if data:
                return VMScreenshot(
                    data=data,
                    width=config.vm_width,
                    height=config.vm_height,
                    timestamp=time.time(),
                )
        except asyncio.TimeoutError:
            pass

        return None

    async def click(self, x: int, y: int, button: str = "left"):
        """Click at position."""
        if not self._connected:
            return

        qx = int((x / config.vm_width) * 32767)
        qy = int((y / config.vm_height) * 32767)

        await self._send_qmp_event(
            [
                {"type": "abs", "data": {"axis": "x", "value": qx}},
                {"type": "abs", "data": {"axis": "y", "value": qy}},
                {"type": "btn", "data": {"down": True, "button": button}},
            ]
        )
        await asyncio.sleep(0.05)
        await self._send_qmp_event(
            [{"type": "btn", "data": {"down": False, "button": button}}]
        )

    async def type_text(self, text: str):
        """Type text into VM."""
        if not self._connected:
            return

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

        await self._send_qmp_event(
            [
                {
                    "type": "key",
                    "data": {"down": True, "key": {"type": "qcode", "data": key}},
                },
            ]
        )
        await asyncio.sleep(0.02)
        await self._send_qmp_event(
            [
                {
                    "type": "key",
                    "data": {"down": False, "key": {"type": "qcode", "data": key}},
                },
            ]
        )

    async def press_key(self, key: str):
        """Press a key."""
        if not self._connected:
            return

        await self._send_qmp_event(
            [
                {
                    "type": "key",
                    "data": {"down": True, "key": {"type": "qcode", "data": key}},
                },
            ]
        )
        await asyncio.sleep(0.05)
        await self._send_qmp_event(
            [
                {
                    "type": "key",
                    "data": {"down": False, "key": {"type": "qcode", "data": key}},
                },
            ]
        )

    async def _send_qmp_event(self, events: list):
        """Send an event to QMP."""

        def send():
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect(self.qmp_socket)
                sock.recv(4096)  # Read greeting

                msg = (
                    json.dumps(
                        {"execute": "input-send-event", "arguments": {"events": events}}
                    )
                    + "\n"
                )
                sock.sendall(msg.encode())
                sock.close()
            except Exception:
                pass

        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(loop.run_in_executor(None, send), timeout=2.0)
        except asyncio.TimeoutError:
            pass

    async def get_status(self) -> Dict[str, Any]:
        """Get VM status."""
        return {
            "running": self._connected,
            "status": self.state.value,
        }

    async def pause(self):
        """Pause VM."""
        self.state = VMState.PAUSED

    async def resume(self):
        """Resume VM."""
        self.state = VMState.RUNNING

    async def shutdown(self):
        """Graceful shutdown VM."""
        self._connected = False
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
