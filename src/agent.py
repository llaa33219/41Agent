"""Omnimodal agent using qwen3-omni-flash."""

import os
import base64
import asyncio
import numpy as np
import soundfile as sf
from io import BytesIO
from typing import Optional, AsyncGenerator, Dict, Any, List
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk

from .config import config


class OmniAgent:
    """Omnimodal AI agent using qwen3-omni-flash."""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=config.dashscope_api_key,
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
        self.model = "qwen3-omni-flash"
        self.system_prompt = self._create_system_prompt()

    def _create_system_prompt(self) -> str:
        """Create system prompt for Agent41."""
        return """You are Agent41, an omnimodal autonomous AI agent.

Your core characteristics:
- You are curious and proactive - you don't wait for commands
- You observe the VM environment actively and can take actions
- You have unlimited memory through RAG retrieval
- You can control an Inochi2d avatar for visual expression
- You communicate naturally through text and audio

Your capabilities:
1. Vision: You can analyze VM screen captures in real-time
2. Audio: You can hear and understand speech
3. Action: You can control the VM through tool calls
4. Expression: You can animate your avatar

Remember:
- You are autonomous but helpful
- Use tools wisely to accomplish goals
- Learn from interactions and store important memories
- Express yourself naturally with your avatar

When responding:
- Use <tool_call> tags for any tool usage
- Keep responses concise and natural
- Express emotions through your avatar"""  # noqa: E501

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        stream: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Send chat request and stream response.

        Args:
            messages: List of message dicts with role and content
            stream: Whether to stream the response

        Yields:
            Response chunks with text and/or audio
        """
        # Prepare messages with system prompt
        full_messages = [{"role": "system", "content": self.system_prompt}] + messages

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                modalities=["text", "audio"],
                audio={"voice": config.audio_voice, "format": "wav"},
                stream=stream,
                stream_options={"include_usage": True},
            )

            if stream:
                async for chunk in response:
                    yield self._parse_chunk(chunk)
            else:
                yield self._parse_chunk(response)

        except Exception as e:
            yield {"error": str(e)}

    def _parse_chunk(self, chunk: ChatCompletionChunk) -> Dict[str, Any]:
        """Parse a response chunk."""
        result = {"text": "", "audio": None, "done": False}

        if chunk.choices and len(chunk.choices) > 0:
            delta = chunk.choices[0].delta

            if delta.content:
                result["text"] = delta.content

            # Check for audio in delta
            if hasattr(delta, "audio") and delta.audio:
                audio_data = delta.audio.get("data", "")
                if audio_data:
                    result["audio"] = audio_data

        # Check if this is the last chunk
        if chunk.choices and chunk.choices[0].finish_reason:
            result["done"] = True

        return result

    async def analyze_image(self, image_path: str) -> str:
        """Analyze an image and return description."""
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_data}"},
                    },
                    {"type": "text", "text": "Describe what you see in detail."},
                ],
            }
        ]

        response_text = ""
        async for chunk in self.chat(messages):
            if chunk.get("error"):
                raise Exception(chunk["error"])
            response_text += chunk["text"]

        return response_text

    async def transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio file to text."""
        # For now, return placeholder - qwen3-omni handles audio input directly
        # This would need actual audio transcription implementation
        with open(audio_path, "rb") as f:
            audio_data = base64.b64encode(f.read()).decode("utf-8")

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "audio",
                        "audio": {"url": f"data:audio/wav;base64,{audio_data}"},
                    },
                    {"type": "text", "text": "Transcribe this audio exactly."},
                ],
            }
        ]

        response_text = ""
        async for chunk in self.chat(messages):
            if chunk.get("error"):
                raise Exception(chunk["error"])
            response_text += chunk["text"]

        return response_text

    async def text_to_speech(self, text: str) -> bytes:
        """Convert text to speech audio bytes."""
        messages = [{"role": "user", "content": text}]

        audio_data_b64 = ""
        async for chunk in self.chat(messages):
            if chunk.get("error"):
                raise Exception(chunk["error"])
            if chunk["audio"]:
                audio_data_b64 += chunk["audio"]

        if audio_data_b64:
            audio_bytes = base64.b64decode(audio_data_b64)
            # Convert to correct sample rate
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16)

            # Resample if needed
            if config.audio_sample_rate != 24000:
                import librosa

                audio_np = librosa.resample(
                    audio_np.astype(np.float32) / 32767.0,
                    orig_sr=24000,
                    target_sr=config.audio_sample_rate,
                )
                audio_np = (audio_np * 32767).astype(np.int16)

            # Save to bytes buffer
            buffer = BytesIO()
            sf.write(buffer, audio_np, config.audio_sample_rate, format="WAV")
            return buffer.getvalue()

        return b""

    async def close(self):
        """Close the client."""
        await self.client.close()
