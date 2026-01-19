"""Main orchestrator for 41Agent."""

import asyncio
import base64
import re
import random
import subprocess
import os
import sys
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from .config import config
from .agent import OmniAgent
from .memory import MemoryManager
from .vm_controller import VMController, VMScreenshot, QEMULauncher
from .avatar_controller import Inochi2dController, AvatarExpression


class Orchestrator:
    """Main orchestrator for 41Agent."""

    def __init__(self):
        self.agent = OmniAgent()
        self.memory = MemoryManager()
        self.vm = VMController()
        self.avatar = Inochi2dController()
        self.running = False
        self.chat_active = False
        self.chat_input = ""
        self.headless = config.headless or not config.check_display()

        # Pygame display
        self.screen = None
        self.clock = None
        self.font = None
        self.chat_font = None

        # Screenshot handling
        self.last_screenshot: Optional[VMScreenshot] = None

        # Auto-launch tracking
        self.vm_process: Optional[subprocess.Popen] = None
        self.inochi_process: Optional[subprocess.Popen] = None

    async def initialize(self):
        """Initialize all components."""
        print(f"Mode: {'Headless' if self.headless else 'GUI'}")

        if self.headless:
            await self._initialize_headless()
        else:
            await self._initialize_gui()

    async def _initialize_gui(self):
        """Initialize with GUI display."""
        import pygame
        from PIL import Image
        import io

        # Initialize pygame
        pygame.init()
        self.screen = pygame.display.set_mode(
            (config.ui_width, config.ui_height), pygame.HWSURFACE | pygame.DOUBLEBUF
        )
        pygame.display.set_caption("41Agent - Omnimodal AI Agent")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.chat_font = pygame.font.Font(None, 48)

        # Connect to VM
        vm_connected = await self.vm.connect()
        if not vm_connected:
            print("Warning: Could not connect to VM. Running in observation mode.")

        # Initialize avatar
        await self.avatar.start()

        # Set initial avatar expression
        await self.avatar.set_expression(AvatarExpression.LISTENING)

        self.running = True
        print("41Agent initialized and ready!")

    async def _initialize_headless(self):
        """Initialize in headless mode (no display)."""
        print("Running in headless mode...")

        # Connect to VM for control
        vm_connected = await self.vm.connect()
        if not vm_connected:
            print("Warning: Could not connect to VM.")

        # Initialize avatar (still works without display)
        await self.avatar.start()
        await self.avatar.set_expression(AvatarExpression.LISTENING)

        self.running = True
        print("41Agent initialized in headless mode!")

    async def run(self):
        """Main run loop."""
        if self.headless:
            await self._run_headless()
        else:
            await self._run_gui()

    async def _run_gui(self):
        """Main run loop with GUI."""
        import pygame
        from PIL import Image
        import io

        screenshot_interval = 1.0 / config.vm_screenshot_fps
        last_screenshot_time = 0.0

        while self.running:
            dt = self.clock.tick(60) / 1000.0

            # Handle events
            await self._handle_events()

            # Capture screenshots
            current_time = pygame.time.get_ticks() / 1000.0
            if current_time - last_screenshot_time >= screenshot_interval:
                self.last_screenshot = await self.vm.get_screenshot()
                last_screenshot_time = current_time

            # Render
            await self._render()

            # Autonomous behavior
            await self._autonomous_behavior()

            # Process AI responses
            await self._process_ai_responses()

        await self.shutdown()

    async def _run_headless(self):
        """Main run loop in headless mode."""
        print("Headless mode: VM and avatar are active.")
        print("Press Ctrl+C to stop.")

        while self.running:
            await asyncio.sleep(1.0)

            # Still process events
            await self._handle_events()

            # Autonomous behavior in headless
            await self._autonomous_behavior()

        await self.shutdown()

    async def _handle_events(self):
        """Handle pygame events."""
        if self.headless:
            # In headless, just check for Ctrl+C
            return

        import pygame

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.chat_active:
                        self.chat_active = False
                        self.chat_input = ""
                        await self.avatar.set_expression(AvatarExpression.LISTENING)
                    else:
                        self.running = False

                elif event.key == pygame.K_t:
                    self.chat_active = not self.chat_active
                    if self.chat_active:
                        await self.avatar.set_expression(AvatarExpression.THINKING)

                elif self.chat_active:
                    if event.key == pygame.K_RETURN:
                        if self.chat_input.strip():
                            await self._send_message(self.chat_input)
                            self.chat_input = ""
                    elif event.key == pygame.K_BACKSPACE:
                        self.chat_input = self.chat_input[:-1]
                    else:
                        if event.unicode and event.unicode.isprintable():
                            self.chat_input += event.unicode

    async def _render(self):
        """Render the display."""
        if self.headless:
            return

        import pygame
        from PIL import Image
        import io

        self.screen.fill((0, 0, 0))

        # Render VM screenshot
        if self.last_screenshot:
            try:
                image = Image.open(io.BytesIO(self.last_screenshot.data))
                image = image.resize((config.ui_width, config.ui_height), Image.LANCZOS)
                surface = pygame.image.fromstring(
                    image.tobytes(), image.size, image.mode
                )
                self.screen.blit(surface, (0, 0))
            except Exception:
                placeholder = self.font.render("VM Screen", True, (255, 255, 255))
                self.screen.blit(
                    placeholder, (config.ui_width // 2 - 50, config.ui_height // 2)
                )

        # Render avatar
        avatar_placeholder = self.font.render("Avatar", True, (255, 255, 255))
        avatar_bg = pygame.Surface((config.avatar_width, config.avatar_height))
        avatar_bg.fill((20, 20, 40))
        self.screen.blit(
            avatar_bg, (config.avatar_position_x, config.avatar_position_y)
        )
        self.screen.blit(
            avatar_placeholder,
            (
                config.avatar_position_x + 50,
                config.avatar_position_y + config.avatar_height // 2,
            ),
        )

        # Render chat UI
        if self.chat_active:
            chat_bg = pygame.Surface((config.ui_width - 100, 80))
            chat_bg.fill((40, 40, 60))
            chat_bg.set_alpha(230)
            self.screen.blit(chat_bg, (50, config.ui_height - 100))

            chat_text = self.chat_font.render(
                f"> {self.chat_input}"
                + ("_" if int(pygame.time.get_ticks() / 500) % 2 else ""),
                True,
                (255, 255, 255),
            )
            self.screen.blit(chat_text, (70, config.ui_height - 80))

        # Render status
        status_text = f"41Agent | {'Headless' if self.headless else 'GUI'}"
        status_surface = self.font.render(status_text, True, (100, 100, 100))
        self.screen.blit(status_surface, (10, 10))

        pygame.display.flip()

    async def _send_message(self, message: str):
        """Send message to AI agent."""
        self.memory.add_to_working("user", message)

        contextual_memory = await self.memory.get_contextual_memory(message)
        messages = self.memory.get_working_messages()

        if contextual_memory:
            messages.insert(
                0,
                {
                    "role": "system",
                    "content": f"Relevant memories:\n{contextual_memory}",
                },
            )

        await self.avatar.start_talking()

        response_text = ""

        async for chunk in self.agent.chat(messages):
            if chunk.get("error"):
                print(f"AI Error: {chunk['error']}")
                await self.avatar.stop_talking()
                await self.avatar.set_expression(AvatarExpression.SAD)
                break

            response_text += chunk["text"]

            if "<tool_call>" in response_text:
                await self.avatar.set_expression(AvatarExpression.THINKING)

            if chunk.get("done"):
                await self.avatar.stop_talking()

                tool_calls = self._extract_tool_calls(response_text)
                if tool_calls:
                    await self._execute_tool_calls(tool_calls)
                else:
                    await self.avatar.set_expression(AvatarExpression.HAPPY)
                    await self.avatar.speak_text(response_text)

                await self.memory.remember(response_text, importance=0.5)
                self.memory.add_to_working("assistant", response_text)
                break

    def _extract_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Extract tool calls from response."""
        tool_calls = []
        pattern = r"<tool_call>(.*?)</tool_call>"
        matches = re.findall(pattern, text, re.DOTALL)

        for match in matches:
            try:
                tool_name_match = re.search(r'"name":\s*"([^"]+)"', match)
                args_match = re.search(r'"args":\s*({.*?})', match, re.DOTALL)

                if tool_name_match:
                    tool_call = {"name": tool_name_match.group(1), "args": {}}
                    if args_match:
                        import json

                        tool_call["args"] = json.loads(args_match.group(1))
                    tool_calls.append(tool_call)
            except Exception as e:
                print(f"Failed to parse tool call: {e}")

        return tool_calls

    async def _execute_tool_calls(self, tool_calls: List[Dict[str, Any]]):
        """Execute tool calls."""
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            args = tool_call.get("args", {})

            try:
                if tool_name == "vm_click":
                    await self.vm.click(
                        args["x"], args.get("y", 0), args.get("button", "left")
                    )

                elif tool_name == "vm_type":
                    await self.vm.type_text(args["text"])

                elif tool_name == "vm_screenshot":
                    screenshot = await self.vm.get_screenshot()
                    if screenshot:
                        await self._analyze_screenshot(screenshot)

                elif tool_name == "vm_press_key":
                    await self.vm.press_key(args["key"])

                elif tool_name == "avatar_expression":
                    await self.avatar.set_expression(
                        AvatarExpression(args["expression"])
                    )

                elif tool_name == "avatar_speak":
                    await self.avatar.speak_text(args["text"])

                elif tool_name == "memory_store":
                    await self.memory.remember(
                        args["content"], importance=args.get("importance", 0.5)
                    )

                elif tool_name == "memory_recall":
                    memories = await self.memory.recall(args["query"], n_results=5)
                    for mem in memories:
                        print(f"Memory: {mem.content}")

            except Exception as e:
                print(f"Tool call failed {tool_name}: {e}")
                await self.avatar.set_expression(AvatarExpression.SAD)

    async def _analyze_screenshot(self, screenshot: VMScreenshot):
        """Analyze VM screenshot with AI."""
        try:
            temp_path = "/tmp/vm_analyze.png"
            with open(temp_path, "wb") as f:
                f.write(screenshot.data)

            description = await self.agent.analyze_image(temp_path)
            print(f"Screen: {description}")
            await self.memory.remember(f"Saw: {description}", importance=0.4)

        except Exception as e:
            print(f"Screenshot analysis failed: {e}")

    async def _process_ai_responses(self):
        """Process pending AI responses."""
        pass

    async def _autonomous_behavior(self):
        """Execute autonomous behaviors."""
        if self.chat_active:
            return

        # Occasional screen analysis
        if self.vm.state.value == "running" and self.last_screenshot:
            if random.random() < 0.01:
                await self._analyze_screenshot(self.last_screenshot)
                await self.avatar.set_expression(AvatarExpression.THINKING)

        # State reset
        if random.random() < 0.001:
            await self.avatar.set_expression(AvatarExpression.LISTENING)

    async def shutdown(self):
        """Shutdown all components."""
        print("Shutting down 41Agent...")

        # Stop avatar
        await self.avatar.stop()

        # Disconnect VM
        await self.vm.disconnect()

        # Close memory
        await self.memory.close()

        # Close agent
        await self.agent.close()

        # Quit pygame
        if not self.headless:
            import pygame

            pygame.quit()

        print("41Agent shutdown complete.")

    async def auto_start_services(self):
        """Auto-start VM and Inochi2d Session."""
        # Start Inochi2d Session
        if config.auto_start_inochi2d:
            inochi_path = Path(config.inochi2d_session_path)
            avatar_path = Path(config.inochi2d_avatar_path)

            if inochi_path.exists() and avatar_path.exists():
                print("Starting Inochi2d Session...")
                self.inochi_process = subprocess.Popen(
                    [str(inochi_path), str(avatar_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                await asyncio.sleep(2)  # Wait for startup
                print("Inochi2d Session started.")

        # Start QEMU VM
        if config.auto_start_vm:
            disk_path = Path(config.vm_disk_path)
            iso_path = Path(config.vm_iso_path)

            if disk_path.exists() or iso_path.exists():
                print("Starting QEMU VM...")
                QEMULauncher.launch(
                    disk_path=str(disk_path) if disk_path.exists() else str(iso_path),
                    iso_path=str(iso_path) if disk_path.exists() else None,
                    memory=config.vm_memory,
                    cpus=config.vm_cpus,
                    socket_path=config.qemu_socket_path,
                    vnc_display=config.qemu_vnc_display,
                )
                await asyncio.sleep(3)  # Wait for VM startup
                print("QEMU VM started.")


async def main():
    """Main entry point."""
    orchestrator = Orchestrator()

    try:
        # Auto-start services
        await orchestrator.auto_start_services()

        # Initialize and run
        await orchestrator.initialize()
        await orchestrator.run()

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if orchestrator.running:
            await orchestrator.shutdown()
