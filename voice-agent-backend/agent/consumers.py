# agent/consumers.py
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from .memory import (
    get_or_create_user,
    get_user_memories,
    create_conversation_session,
    add_event,
    build_transcript,
    update_memories_from_transcript,
)
from .realtime_bridge import RealtimeBridge


class VoiceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # user_id from query string: /ws/voice/?user_id=123
        self.user_id = self.scope["query_string"].decode().split("user_id=")[-1] or "anonymous"

        await self.accept()

        # Prepare memory + Realtime connection
        user = get_or_create_user(self.user_id)
        memories = get_user_memories(self.user_id)
        self.session = create_conversation_session(user)

        memory_text = "\n".join(f"- {m}" for m in memories) or "- (no previous memories)"
        system_instructions = f"""
You are a friendly real-time voice assistant.

You know these things about the user from past interactions:
{memory_text}

Use this information to personalize responses, but if the user corrects something,
always believe the user and implicitly update your understanding.
Keep your answers concise and conversational.
"""

        async def on_text(text_delta: str, is_final: bool):
            # Send text delta to client
            await self.send_json(
                {
                    "type": "ai_text_delta",
                    "text": text_delta,
                    "is_final": is_final,
                }
            )
            if text_delta:
                # Store assistant message fragments as events
                add_event(self.session, "assistant", text_delta)

        async def on_audio_chunk(pcm_bytes: bytes):
            # Send audio to client as binary
            await self.send(bytes_data=pcm_bytes)

        self.bridge = RealtimeBridge(
            system_instructions=system_instructions,
            on_text=on_text,
            on_audio_chunk=on_audio_chunk,
        )

        await self.bridge.connect()
        await self.send_json({"type": "ready"})

    async def disconnect(self, close_code):
        # On disconnect, build transcript, update memories
        try:
            transcript = build_transcript(self.session)
            await update_memories_from_transcript(self.user_id, transcript)
        except Exception as e:
            print("Memory update failed:", e)
        if hasattr(self, "bridge"):
            await self.bridge.close()

    async def receive(self, text_data=None, bytes_data=None):
        # Binary = audio frames; Text = control messages
        if bytes_data is not None:
            # Audio from client
            await self.bridge.send_audio_chunk(bytes_data)
            return

        if text_data is not None:
            data = json.loads(text_data)
            msg_type = data.get("type")

            if msg_type == "start_session":
                # Already connected; no-op or reset logic
                return

            elif msg_type == "user_transcript":
                # If you do STT client-side and send the text
                add_event(self.session, "user", data.get("text", ""))

            elif msg_type == "stop_speaking":
                await self.bridge.commit_and_request_response()

            elif msg_type == "end_session":
                await self.close()
