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
            additional_headers  ={
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
                # Usually everything from Realtime is JSON text, so bytes here are rare.
                print("WS BYTES FROM REALTIME:", len(msg))
                continue

            event = json.loads(msg)
            etype = event.get("type")
            print("REALTIME EVENT:", etype)  # keep this for debugging

            # 1) ASSISTANT TRANSCRIPT (text of the AI's spoken reply)
            if etype == "response.audio_transcript.delta":
                # This is a partial text transcript of the model's audio **response**
                text = event["delta"]          # <--- IMPORTANT: it's directly in "delta"
                await self.on_text(text, False)

            elif etype == "response.audio_transcript.done":
                # Full transcript done
                await self.on_text("", True)

            # 2) ASSISTANT AUDIO (base64-encoded PCM16)
            # elif etype == "response.audio.delta":
            elif etype == "response.audio.delta":
                # event["delta"] is a base64-encoded audio chunk
                b64_audio = event["delta"]
                pcm_bytes = base64.b64decode(b64_audio)
                await self.on_audio_chunk(pcm_bytes)

            elif etype == "response.audio.done":
                # No more audio for this response – optional to handle
                print("AUDIO DONE")

            # 3) OPTIONAL: transcription of *your* input audio
            elif etype == "conversation.item.input_audio_transcription.delta":
                # If you want to see what the model heard from the user:
                print("USER TRANSCRIPT DELTA:", event["delta"])
            elif etype == "conversation.item.input_audio_transcription.completed":
                print("USER TRANSCRIPT COMPLETE:", event.get("transcript"))

            # 4) REAL errors
            elif etype == "response.error" or etype == "error":
                print("REALTIME ERROR EVENT:", event)

            else:
                # Useful during development – you can comment this out later
                print("UNHANDLED EVENT:", event)


    # async def _listen_loop(self):
    #     assert self.ws is not None
    #     async for msg in self.ws:
    #         if isinstance(msg, bytes):
    #             print("WS BYTES FROM REALTIME:", len(msg))
    #             continue

    #         event = json.loads(msg)
    #         etype = event.get("type")
    #         print("REALTIME EVENT:", etype)

    #         # Adjust to the exact event names from the Realtime docs
    #         if etype == "response.output_text.delta":
    #             text = event["delta"]["text"]
    #             await self.on_text(text, False)

    #         elif etype == "response.output_text.completed":
    #             await self.on_text("", True)

    #         elif etype == "response.audio.delta":
    #             print("REALTIME ERROR:", event)
    #             b64 = event["delta"]["audio"]
    #             pcm = base64.b64decode(b64)
    #             await self.on_audio_chunk(pcm)


    async def send_audio_chunk(self, pcm_bytes: bytes):
        assert self.ws is not None
        b64 = base64.b64encode(pcm_bytes).decode()
        event = {
            "type": "input_audio_buffer.append",
            "audio": b64,
            # "audio_format": "pcm16",
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