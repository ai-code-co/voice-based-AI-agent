import os
import json
import base64
import asyncio
import websockets
from typing import Callable, Awaitable, Optional

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview")

REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={REALTIME_MODEL}"


class RealtimeBridge:
    def __init__(
        self,
        system_instructions: str,
        on_text: Callable[[str, bool], Awaitable[None]],
        on_audio_chunk: Callable[[bytes], Awaitable[None]],
    ):
        self.system_instructions = system_instructions
        self.on_text = on_text
        self.on_audio_chunk = on_audio_chunk
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._listen_task: Optional[asyncio.Task] = None

    async def connect(self):
        self.ws = await websockets.connect(
            REALTIME_URL,
            extra_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1",
            },
        )

        session_update = {
            "type": "session.update",
            "session": {
                "instructions": self.system_instructions,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "modalities": ["audio", "text"],
                "voice": "verse",
            },
        }
        await self.ws.send(json.dumps(session_update))

        self._listen_task = asyncio.create_task(self._listen_loop())

    async def close(self):
        if self.ws:
            await self.ws.close()
        if self._listen_task:
            self._listen_task.cancel()

    async def _listen_loop(self):
        assert self.ws is not None
        async for msg in self.ws:
            if isinstance(msg, bytes):
                continue

            event = json.loads(msg)
            etype = event.get("type")

            # Adjust to the exact event names from the Realtime docs
            if etype == "response.output_text.delta":
                text = event["delta"]["text"]
                await self.on_text(text, False)

            elif etype == "response.output_text.completed":
                await self.on_text("", True)

            elif etype == "response.audio.delta":
                b64 = event["delta"]["audio"]
                pcm = base64.b64decode(b64)
                await self.on_audio_chunk(pcm)

    async def send_audio_chunk(self, pcm_bytes: bytes):
        assert self.ws is not None
        b64 = base64.b64encode(pcm_bytes).decode()
        event = {
            "type": "input_audio_buffer.append",
            "audio": b64,
            "audio_format": "pcm16",
        }
        await self.ws.send(json.dumps(event))

    async def commit_and_request_response(self):
        assert self.ws is not None

        await self.ws.send(json.dumps({"type": "input_audio_buffer.commit"}))

        response_create = {
            "type": "response.create",
            "response": {
                "modalities": ["audio", "text"],
                "instructions": "Answer the user's last utterance.",
            },
        }
        await self.ws.send(json.dumps(response_create))
