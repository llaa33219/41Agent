"""Inochi2d avatar controller via VMC protocol."""

import asyncio
import math
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from pythonosc import udp_client

from .config import config


class AvatarExpression(Enum):
    """Avatar expressions."""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    SURPRISED = "surprised"
    ANGRY = "angry"
    THINKING = "thinking"
    TALKING = "talking"
    LISTENING = "listening"


@dataclass
class AvatarState:
    """Current avatar state."""

    expression: AvatarExpression = AvatarExpression.NEUTRAL
    mouth_open: float = 0.0
    eye_blink_left: float = 0.0
    eye_blink_right: float = 0.0
    brow_raise: float = 0.0
    mouth_smile: float = 0.0
    eye_gaze_x: float = 0.0
    eye_gaze_y: float = 0.0
    head_tilt: float = 0.0
    is_talking: bool = False


class Inochi2dController:
    """Controller for Inochi2d avatar via VMC protocol."""

    def __init__(self):
        self.client = udp_client.SimpleUDPClient(
            config.inochi2d_vmc_host, config.inochi2d_vmc_port
        )
        self.state = AvatarState()
        self.running = False
        self.animation_task: Optional[asyncio.Task] = None
        self.expression_start_time: float = 0.0

    async def start(self):
        """Start the avatar controller."""
        self.running = True
        self.animation_task = asyncio.create_task(self._animation_loop())
        await self.set_expression(AvatarExpression.NEUTRAL)

    async def stop(self):
        """Stop the avatar controller."""
        self.running = False
        if self.animation_task:
            self.animation_task.cancel()
            try:
                await self.animation_task
            except asyncio.CancelledError:
                pass
        # Reset avatar
        await self.reset()

    async def reset(self):
        """Reset avatar to neutral position."""
        self._send_parameter("MouthOpen", 0.0)
        self._send_parameter("EyeBlinkLeft", 0.0)
        self._send_parameter("EyeBlinkRight", 0.0)
        self._send_parameter("BrowInnerUp", 0.0)
        self._send_parameter("MouthSmileLeft", 0.0)
        self._send_parameter("EyeLookUpLeft", 0.5)
        self._send_parameter("EyeLookDownLeft", 0.5)
        self.state = AvatarState()

    async def set_expression(self, expression: AvatarExpression):
        """Set avatar expression.

        Args:
            expression: Expression to set
        """
        self.state.expression = expression
        self.expression_start_time = time.time()

        # Reset base values
        self._send_parameter("MouthOpen", 0.0)
        self._send_parameter("EyeBlinkLeft", 0.0)
        self._send_parameter("EyeBlinkRight", 0.0)
        self._send_parameter("BrowInnerUp", 0.0)
        self._send_parameter("MouthSmileLeft", 0.0)

        # Set expression-specific values
        expression_values = {
            AvatarExpression.NEUTRAL: {},
            AvatarExpression.HAPPY: {"MouthSmileLeft": 1.0, "BrowInnerUp": 0.5},
            AvatarExpression.SAD: {"BrowInnerUp": -0.5, "MouthSmileLeft": -0.5},
            AvatarExpression.SURPRISED: {
                "MouthOpen": 0.5,
                "EyeBlinkLeft": 0.0,
                "BrowInnerUp": 1.0,
            },
            AvatarExpression.ANGRY: {"BrowInnerUp": -0.8, "MouthSmileLeft": -0.3},
            AvatarExpression.THINKING: {"BrowInnerUp": 0.3, "EyeLookUpLeft": 0.8},
            AvatarExpression.LISTENING: {"EyeBlinkLeft": 0.0, "BrowInnerUp": 0.2},
        }

        for param, value in expression_values.get(expression, {}).items():
            self._send_parameter(param, value)

    async def start_talking(self):
        """Start talking animation."""
        self.state.is_talking = True

    async def stop_talking(self):
        """Stop talking animation."""
        self.state.is_talking = False
        self._send_parameter("MouthOpen", 0.0)

    async def set_mouth_open(self, value: float):
        """Set mouth openness (0.0 to 1.0).

        Args:
            value: Openness value
        """
        self._send_parameter("MouthOpen", value)
        self.state.mouth_open = value

    async def blink(self):
        """Trigger a blink."""
        self._send_parameter("EyeBlinkLeft", 1.0)
        self._send_parameter("EyeBlinkRight", 1.0)
        await asyncio.sleep(0.1)
        self._send_parameter("EyeBlinkLeft", 0.0)
        self._send_parameter("EyeBlinkRight", 0.0)

    async def look_at(self, x: float, y: float):
        """Set eye gaze direction.

        Args:
            x: X direction (-1.0 left to 1.0 right)
            y: Y direction (-1.0 down to 1.0 up)
        """
        self._send_parameter("EyeLookUpLeft", 0.5 + y * 0.5)
        self._send_parameter("EyeLookDownLeft", 0.5 + y * 0.5)
        self._send_parameter("EyeLookUpRight", 0.5 + y * 0.5)
        self._send_parameter("EyeLookDownRight", 0.5 + y * 0.5)
        self.state.eye_gaze_x = x
        self.state.eye_gaze_y = y

    async def set_eyebrows(self, raise_level: float):
        """Set eyebrow raise level.

        Args:
            raise_level: Raise level (-1.0 to 1.0)
        """
        self._send_parameter("BrowInnerUp", raise_level)
        self.state.brow_raise = raise_level

    async def set_mouth_smile(self, value: float):
        """Set mouth smile amount.

        Args:
            value: Smile amount (-1.0 to 1.0)
        """
        self._send_parameter("MouthSmileLeft", value)
        self._send_parameter("MouthSmileRight", value)
        self.state.mouth_smile = value

    async def nod(self):
        """Perform a nod animation."""
        self._send_parameter("JawOpen", 0.2)
        await asyncio.sleep(0.2)
        self._send_parameter("JawOpen", 0.0)
        await asyncio.sleep(0.1)
        self._send_parameter("JawOpen", 0.2)
        await asyncio.sleep(0.2)
        self._send_parameter("JawOpen", 0.0)

    async def shake_head(self):
        """Perform a head shake animation."""
        self._send_parameter("HeadPosX", 0.1)
        await asyncio.sleep(0.1)
        self._send_parameter("HeadPosX", -0.1)
        await asyncio.sleep(0.1)
        self._send_parameter("HeadPosX", 0.1)
        await asyncio.sleep(0.1)
        self._send_parameter("HeadPosX", -0.1)
        await asyncio.sleep(0.1)
        self._send_parameter("HeadPosX", 0.0)

    def _send_parameter(self, name: str, value: float):
        """Send a parameter value via VMC protocol.

        Args:
            name: Parameter name
            value: Parameter value
        """
        try:
            self.client.send_message("/VMC/Ext/Blend/Val", [name, value])
        except Exception as e:
            print(f"Failed to send VMC message: {e}")

    async def _animation_loop(self):
        """Background animation loop for talking and blinking."""
        last_blink_time = time.time()
        blink_interval = 3.0  # Blink every 3 seconds
        t = 0.0

        while self.running:
            try:
                current_time = time.time()

                # Talking animation
                if self.state.is_talking:
                    # Mouth movement based on sine wave
                    mouth_value = (math.sin(t * 15) + 1) / 2 * 0.8
                    self._send_parameter("MouthOpen", mouth_value)
                    self.state.mouth_open = mouth_value

                # Automatic blinking
                if current_time - last_blink_time > blink_interval:
                    await self.blink()
                    last_blink_time = current_time

                # Subtle idle animation
                idle_brow = math.sin(t * 0.5) * 0.1
                self._send_parameter("BrowInnerUp", idle_brow)
                self.state.brow_raise = idle_brow

                await asyncio.sleep(1 / 60)  # 60fps
                t += 1 / 60

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Animation loop error: {e}")
                await asyncio.sleep(0.1)

    def get_state(self) -> AvatarState:
        """Get current avatar state."""
        return self.state

    async def speak_text(self, text: str):
        """Animate avatar to speak text.

        Args:
            text: Text to animate for
        """
        await self.start_talking()

        # Simple word-based timing
        words = text.split()
        for i, word in enumerate(words):
            # Vary mouth openness for each word
            mouth_value = 0.3 + (len(word) / 20) * 0.5
            self._send_parameter("MouthOpen", min(mouth_value, 1.0))
            await asyncio.sleep(0.1 + len(word) * 0.02)
            self._send_parameter("MouthOpen", 0.1)
            await asyncio.sleep(0.05)

            # Occasional blinks during speech
            if i % 5 == 0:
                await self.blink()

        await self.stop_talking()


class AvatarRenderer:
    """Simple avatar renderer using Pygame for embedding."""

    def __init__(self, width: int, height: int, position: tuple):
        """Initialize avatar renderer.

        Args:
            width: Avatar display width
            height: Avatar display height
            position: (x, y) position on screen
        """
        self.width = width
        self.height = height
        self.position = position
        self.controller = Inochi2dController()
        self.surface = None

    async def initialize(self):
        """Initialize the renderer."""
        await self.controller.start()

    async def update(self, dt: float):
        """Update avatar rendering.

        Args:
            dt: Delta time
        """
        # VMC protocol handles actual avatar rendering
        # This is just a placeholder for potential custom rendering
        pass

    async def close(self):
        """Close the renderer."""
        await self.controller.stop()
