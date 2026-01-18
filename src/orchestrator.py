"""Main orchestrator for 41Agent."""

import asyncio
import base64
import re
import random
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

import pygame
from PIL import Image
import io

from .config import config
from .agent import OmniAgent
from .memory import MemoryManager
from .vm_controller import VMController, VMScreenshot
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

        # Pygame display
        self.screen = None
        self.clock = None
        self.font = None
        self.chat_font = None

        # Screenshot handling
        self.last_screenshot: Optional[VMScreenshot] = None
        self.screenshot_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize all components."""
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

    async def run(self):
        """Main run loop."""
        screenshot_interval = 1.0 / config.vm_screenshot_fps
        last_screenshot_time = 0.0

        while self.running:
            dt = self.clock.tick(60) / 1000.0  # 60 FPS

            # Handle events
            await self._handle_events()

            # Capture screenshots at configured FPS
            current_time = pygame.time.get_ticks() / 1000.0
            if current_time - last_screenshot_time >= screenshot_interval:
                self.last_screenshot = await self.vm.get_screenshot()
                last_screenshot_time = current_time

            # Render
            await self._render()

            # Autonomous behavior
            await self._autonomous_behavior()

            # Process any pending AI responses
            await self._process_ai_responses()

        await self.shutdown()

    async def _handle_events(self):
        """Handle pygame events."""
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
                    elif event.key == pygame.K_LCTRL or event.key == pygame.K_RCTRL:
                        pass  # Skip control keys
                    else:
                        # Add character
                        if event.unicode and event.unicode.isprintable():
                            self.chat_input += event.unicode

    async def _render(self):
        """Render the display."""
        self.screen.fill((0, 0, 0))

        # Render VM screenshot if available
        if self.last_screenshot:
            try:
                image = Image.open(io.BytesIO(self.last_screenshot.data))
                image = image.resize((config.ui_width, config.ui_height), Image.LANCZOS)
                surface = pygame.image.fromstring(
                    image.tobytes(), image.size, image.mode
                )
                self.screen.blit(surface, (0, 0))
            except Exception as e:
                # Fallback: show placeholder
                placeholder = self.font.render(
                    "VM Screen Capture", True, (255, 255, 255)
                )
                self.screen.blit(
                    placeholder, (config.ui_width // 2 - 100, config.ui_height // 2)
                )

        # Render avatar in bottom-right corner
        avatar_placeholder = self.font.render(
            f"Inochi2d Avatar ({config.avatar_width}x{config.avatar_height})",
            True,
            (255, 255, 255),
        )
        avatar_bg = pygame.Surface((config.avatar_width, config.avatar_height))
        avatar_bg.fill((20, 20, 40))
        self.screen.blit(
            avatar_bg, (config.avatar_position_x, config.avatar_position_y)
        )
        self.screen.blit(
            avatar_placeholder,
            (
                config.avatar_position_x + 20,
                config.avatar_position_y + config.avatar_height // 2 - 20,
            ),
        )

        # Render chat UI if active
        if self.chat_active:
            # Chat input box
            chat_bg = pygame.Surface((config.ui_width - 100, 80))
            chat_bg.fill((40, 40, 60))
            chat_bg.set_alpha(230)
            self.screen.blit(chat_bg, (50, config.ui_height - 100))

            # Chat text
            chat_text = self.chat_font.render(
                f"> {self.chat_input}"
                + ("_" if int(pygame.time.get_ticks() / 500) % 2 else ""),
                True,
                (255, 255, 255),
            )
            self.screen.blit(chat_text, (70, config.ui_height - 80))

            # Instructions
            help_text = self.font.render(
                "Press ENTER to send, ESC to close", True, (150, 150, 150)
            )
            self.screen.blit(help_text, (50, config.ui_height - 30))

        # Render status indicator
        status_text = f"41Agent | VM: {'Connected' if self.vm.state.value == 'running' else 'Disconnected'} | Chat: {'Active' if self.chat_active else 'Press T'}"
        status_surface = self.font.render(status_text, True, (100, 100, 100))
        self.screen.blit(status_surface, (10, 10))

        pygame.display.flip()

    async def _send_message(self, message: str):
        """Send message to AI agent."""
        # Add to working memory
        self.memory.add_to_working("user", message)

        # Get contextual memory
        contextual_memory = await self.memory.get_contextual_memory(message)

        # Build messages
        messages = self.memory.get_working_messages()

        # Add contextual memory as system context
        if contextual_memory:
            messages.insert(
                0,
                {
                    "role": "system",
                    "content": f"Relevant memories:\n{contextual_memory}",
                },
            )

        # Start talking animation
        await self.avatar.start_talking()

        # Send to AI
        response_text = ""
        tool_calls = []

        async for chunk in self.agent.chat(messages):
            if chunk.get("error"):
                print(f"AI Error: {chunk['error']}")
                await self.avatar.stop_talking()
                await self.avatar.set_expression(AvatarExpression.SAD)
                break

            response_text += chunk["text"]

            # Check for tool calls in response
            if "<tool_call>" in response_text:
                await self.avatar.set_expression(AvatarExpression.THINKING)

            if chunk.get("done"):
                await self.avatar.stop_talking()

                # Extract and process tool calls
                tool_calls = self._extract_tool_calls(response_text)
                if tool_calls:
                    await self._execute_tool_calls(tool_calls)
                else:
                    # Just a text response
                    await self.avatar.set_expression(AvatarExpression.HAPPY)
                    await self.avatar.speak_text(response_text)

                # Store in memory
                await self.memory.remember(response_text, importance=0.5)

                # Add to working memory
                self.memory.add_to_working("assistant", response_text)

                break

    def _extract_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Extract tool calls from response text.

        Args:
            text: Response text containing tool calls

        Returns:
            List of tool call dictionaries
        """
        tool_calls = []

        # Pattern: <tool_call>...</tool_call>
        pattern = r"<tool_call>(.*?)</tool_call>"
        matches = re.findall(pattern, text, re.DOTALL)

        for match in matches:
            try:
                # Parse tool call
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
        """Execute tool calls.

        Args:
            tool_calls: List of tool calls to execute
        """
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            args = tool_call.get("args", {})

            try:
                if tool_name == "vm_click":
                    await self.vm.click(
                        args["x"], args.get("y", 0), args.get("button", "left")
                    )
                    await self.memory.remember(
                        f"Clicked at ({args['x']}, {args.get('y', 0)})", importance=0.3
                    )

                elif tool_name == "vm_type":
                    await self.vm.type_text(args["text"])
                    await self.memory.remember(
                        f"Typed: {args['text'][:50]}...", importance=0.3
                    )

                elif tool_name == "vm_screenshot":
                    screenshot = await self.vm.get_screenshot()
                    if screenshot:
                        # Analyze the screenshot
                        await self._analyze_screenshot(screenshot)

                elif tool_name == "vm_press_key":
                    await self.vm.press_key(args["key"])

                elif tool_name == "avatar_expression":
                    expression = AvatarExpression(args["expression"])
                    await self.avatar.set_expression(expression)

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
                print(f"Failed to execute tool call {tool_name}: {e}")
                await self.avatar.set_expression(AvatarExpression.SAD)

    async def _analyze_screenshot(self, screenshot: VMScreenshot):
        """Analyze VM screenshot with AI.

        Args:
            screenshot: Screenshot to analyze
        """
        try:
            # Save temporary screenshot
            temp_path = "/tmp/vm_analyze.png"
            with open(temp_path, "wb") as f:
                f.write(screenshot.data)

            # Analyze with AI
            description = await self.agent.analyze_image(temp_path)
            print(f"Screen analysis: {description}")

            # Store in memory
            await self.memory.remember(f"Saw on screen: {description}", importance=0.4)

        except Exception as e:
            print(f"Failed to analyze screenshot: {e}")

    async def _process_ai_responses(self):
        """Process any pending AI responses (for autonomous mode)."""
        # This handles async AI responses when agent acts autonomously
        pass

    async def _autonomous_behavior(self):
        """Execute autonomous behaviors when not in chat mode."""
        if self.chat_active:
            return

        # Occasionally analyze screen if VM is connected
        if self.vm.state.value == "running" and self.last_screenshot:
            # Small chance to analyze screen autonomously
            import random

            if random.random() < 0.01:  # 1% chance per frame
                await self._analyze_screenshot(self.last_screenshot)
                await self.avatar.set_expression(AvatarExpression.THINKING)

        # Return to listening after a while
        if random.random() < 0.001:  # Occasional state reset
            await self.avatar.set_expression(AvatarExpression.LISTENING)

    async def shutdown(self):
        """Shutdown all components."""
        print("Shutting down 41Agent...")

        # Disconnect VM
        await self.vm.disconnect()

        # Stop avatar
        await self.avatar.stop()

        # Close memory
        await self.memory.close()

        # Close agent
        await self.agent.close()

        # Quit pygame
        pygame.quit()

        print("41Agent shutdown complete.")


async def main():
    """Main entry point."""
    orchestrator = Orchestrator()

    try:
        await orchestrator.initialize()
        await orchestrator.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        raise
    finally:
        if orchestrator.running:
            await orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
