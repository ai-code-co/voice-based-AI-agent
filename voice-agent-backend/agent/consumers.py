# agent/consumers.py
import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

from .memory import (
    get_or_create_user,
    get_user_memories,
    create_conversation_session,
    add_event,
    build_transcript,
    update_memories_from_transcript,
)
from .realtime_bridge import RealtimeBridge


class VoiceConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # user_id from query string: /ws/voice/?user_id=123
        query = self.scope["query_string"].decode()
        user_id = "anonymous"
        if "user_id=" in query:
            user_id = query.split("user_id=")[-1] or "anonymous"
        self.user_id = user_id

        await self.accept()

        # ---- DB operations via database_sync_to_async ----
        self.user = await database_sync_to_async(get_or_create_user)(self.user_id)
        memories = await database_sync_to_async(get_user_memories)(self.user_id)
        self.session = await database_sync_to_async(create_conversation_session)(self.user)

        memory_text = "\n".join(f"- {m}" for m in memories) or "- (no previous memories)"
        system_instructions = f"""
You are a friendly real-time voice assistant.

You know these things about the user from past interactions:
{memory_text}

Language rules (very important):
- Always respond in ENGLISH only.
- Do NOT use Spanish, Korean, or any other language unless the user clearly speaks in that language AND explicitly asks you to reply in that language.
- If the user speaks in a mix of languages, answer ONLY in English.
- Never start responses with '¡Claro!', 'Hola', '안녕하세요', or similar non-English greetings.

Style:
- Keep answers short and conversational (2–4 sentences).
- Speak like you are talking, not writing an essay.
"""




        async def on_text(text_delta: str, is_final: bool):
            # Send text delta to client
            print("SENDING TEXT DELTA TO CLIENT:", repr(text_delta), "final?", is_final)

            await self.send_json(
                {
                    "type": "ai_text_delta",
                    "text": text_delta,
                    "is_final": is_final,
                }
            )

            if text_delta:
                # Store assistant message fragments as events (DB write)
                await database_sync_to_async(add_event)(
                    self.session, "assistant", text_delta
                )

        async def on_audio_chunk(pcm_bytes: bytes):
            print("SENDING AUDIO CHUNK TO CLIENT, len:", len(pcm_bytes))
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
            transcript = await database_sync_to_async(build_transcript)(self.session)
            await database_sync_to_async(update_memories_from_transcript)(
                self.user_id, transcript
            )
        except Exception as e:
            print("Memory update failed:", e)
        if hasattr(self, "bridge"):
            await self.bridge.close()

    async def receive(self, text_data=None, bytes_data=None):
        # Binary = audio frames; Text = control messages
        if bytes_data is not None:
            # Audio from client
            print("RECEIVED AUDIO BYTES FROM CLIENT:", len(bytes_data))
            await self.bridge.send_audio_chunk(bytes_data)
            return

        if text_data is not None:
            data = json.loads(text_data)
            msg_type = data.get("type")
            print("RECEIVED TEXT MESSAGE FROM CLIENT:", data)

            if msg_type == "start_session":
                # Already connected; no-op or reset logic
                return

            elif msg_type == "user_transcript":
                # If you do STT client-side and send the text
                await database_sync_to_async(add_event)(
                    self.session, "user", data.get("text", "")
                )

            elif msg_type == "stop_speaking":
                print("STOP_SPEAKING from client → committing & requesting response")
                await self.bridge.commit_and_request_response()

            elif msg_type == "end_session":
                await self.close()


# # agent/consumers.py
# import json
# import asyncio
# from channels.generic.websocket import AsyncJsonWebsocketConsumer
# from .memory import (
#     get_or_create_user,
#     get_user_memories,
#     create_conversation_session,
#     add_event,
#     build_transcript,
#     update_memories_from_transcript,
# )
# from .realtime_bridge import RealtimeBridge


# class VoiceConsumer(AsyncJsonWebsocketConsumer):
#     async def connect(self):
#         # user_id from query string: /ws/voice/?user_id=123
#         self.user_id = self.scope["query_string"].decode().split("user_id=")[-1] or "anonymous"

#         await self.accept()

#         # Prepare memory + Realtime connection
#         user = await get_or_create_user(self.user_id)
#         memories =await get_user_memories(self.user_id)
#         self.session =await create_conversation_session(user)

#         memory_text = "\n".join(f"- {m}" for m in memories) or "- (no previous memories)"
#         system_instructions = f"""
# You are a friendly real-time voice assistant.

# You know these things about the user from past interactions:
# {memory_text}

# Use this information to personalize responses, but if the user corrects something,
# always believe the user and implicitly update your understanding.
# Keep your answers concise and conversational.
# """

#         async def on_text(text_delta: str, is_final: bool):
#             # Send text delta to client
#             print("SENDING TEXT DELTA TO CLIENT:", repr(text_delta), "final?", is_final)

#             await self.send_json(
#                 {
#                     "type": "ai_text_delta",
#                     "text": text_delta,
#                     "is_final": is_final,
#                 }
#             )

 

#             if text_delta:
#                 # Store assistant message fragments as events
#                 add_event(self.session, "assistant", text_delta)

#         async def on_audio_chunk(pcm_bytes: bytes):
#             print("SENDING AUDIO CHUNK TO CLIENT, len:", len(pcm_bytes))
#             # Send audio to client as binary
#             await self.send(bytes_data=pcm_bytes)

#         self.bridge = RealtimeBridge(
#             system_instructions=system_instructions,
#             on_text=on_text,
#             on_audio_chunk=on_audio_chunk,
#         )

#         await self.bridge.connect()
#         await self.send_json({"type": "ready"})
     

#     async def disconnect(self, close_code):
#         # On disconnect, build transcript, update memories
#         try:
#             transcript = build_transcript(self.session)
#             await update_memories_from_transcript(self.user_id, transcript)
#         except Exception as e:
#             print("Memory update failed:", e)
#         if hasattr(self, "bridge"):
#             await self.bridge.close()

#     async def receive(self, text_data=None, bytes_data=None):
#         # Binary = audio frames; Text = control messages
#         if bytes_data is not None:
#             # Audio from client
#             await self.bridge.send_audio_chunk(bytes_data)
#             return

#         if text_data is not None:
#             data = json.loads(text_data)
#             msg_type = data.get("type")

#             if msg_type == "start_session":
#                 # Already connected; no-op or reset logic
#                 return

#             elif msg_type == "user_transcript":
#                 # If you do STT client-side and send the text
#                 add_event(self.session, "user", data.get("text", ""))

#             elif msg_type == "stop_speaking":
#                 print("STOP_SPEAKING from client → committing & requesting response")
#                 await self.bridge.commit_and_request_response()

#             elif msg_type == "end_session":
#                 await self.close()
