# agent/memory.py
import os
import json
from typing import List
from .models import (
    UserProfile,
    UserMemory,
    ConversationSession,
    ConversationEvent,
    MemoryType,
)
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")


def get_or_create_user(user_id: str) -> UserProfile:
    user, _created = UserProfile.objects.get_or_create(id=user_id)
    return user


def get_user_memories(user_id: str, limit: int = 20) -> List[str]:
    qs = (
        UserMemory.objects.filter(user_id=user_id)
        .order_by("-importance", "-updated_at")[:limit]
    )
    return [m.content for m in qs]


def create_conversation_session(user: UserProfile) -> ConversationSession:
    return ConversationSession.objects.create(user=user)


def add_event(session: ConversationSession, role: str, content: str):
    ConversationEvent.objects.create(session=session, role=role, content=content)


def build_transcript(session: ConversationSession) -> str:
    events = session.events.order_by("created_at")
    lines = [f"{e.role.upper()}: {e.content}" for e in events]
    return "\n".join(lines)


def update_memories_from_transcript(user_id: str, transcript: str):
    """
    SYNC memory extraction using a normal chat model.
    This will be called via database_sync_to_async from the consumer.
    """
    client = openai.OpenAI(api_key=openai.api_key)

    prompt = f"""
You are a memory extraction assistant.

From the conversation transcript below, extract:
- stable user preferences
- stable user profile facts
- a short summary of what happened in this session

Return JSON like:
{{
  "memories": [
    {{"type": "preference" | "fact" | "history_summary", "content": "string", "importance": 1-10}}
  ]
}}

Transcript:
\"\"\"{transcript}\"\"\"
"""

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    data = json.loads(resp.choices[0].message.content)
    memories = data.get("memories", [])

    user = get_or_create_user(user_id)

    for mem in memories:
        UserMemory.objects.create(
            user=user,
            type=mem["type"],
            content=mem["content"],
            importance=int(mem.get("importance", 5)),
        )


# import os
# import json
# from typing import List
# from django.utils import timezone
# from channels.db import database_sync_to_async
# from .models import (
#     UserProfile,
#     UserMemory,
#     ConversationSession,
#     ConversationEvent,
#     MemoryType,
# )
# import openai

# openai.api_key = os.getenv("OPENAI_API_KEY")

# @database_sync_to_async
# def get_or_create_user(user_id: str) -> UserProfile:
#     user, _created = UserProfile.objects.get_or_create(id=user_id)
#     return user

# @database_sync_to_async
# def get_user_memories(user_id: str, limit: int = 20) -> List[str]:
#     qs = (
#         UserMemory.objects.filter(user_id=user_id)
#         .order_by("-importance", "-updated_at")[:limit]
#     )
#     return [m.content for m in qs]

# @database_sync_to_async
# def create_conversation_session(user: UserProfile) -> ConversationSession:
#     return ConversationSession.objects.create(user=user)


# def add_event(session: ConversationSession, role: str, content: str):
#     ConversationEvent.objects.create(session=session, role=role, content=content)


# def build_transcript(session: ConversationSession) -> str:
#     events = session.events.order_by("created_at")
#     lines = [f"{e.role.upper()}: {e.content}" for e in events]
#     return "\n".join(lines)


# async def update_memories_from_transcript(user_id: str, transcript: str):
#     """
#     Async memory extraction using a normal chat model.
#     """
#     client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#     prompt = f"""
# You are a memory extraction assistant.

# From the conversation transcript below, extract:
# - stable user preferences
# - stable user profile facts
# - a short summary of what happened in this session

# Return JSON like:
# {{
#   "memories": [
#     {{"type": "preference" | "fact" | "history_summary", "content": "string", "importance": 1-10}}
#   ]
# }}

# Transcript:
# \"\"\"{transcript}\"\"\"
# """

#     resp = await client.chat.completions.create(
#         model="gpt-4.1-mini",
#         messages=[{"role": "user", "content": prompt}],
#         response_format={"type": "json_object"},
#     )

#     data = json.loads(resp.choices[0].message.content)
#     memories = data.get("memories", [])

#     user = get_or_create_user(user_id)

#     for mem in memories:
#         UserMemory.objects.create(
#             user=user,
#             type=mem["type"],
#             content=mem["content"],
#             importance=int(mem.get("importance", 5)),
#         )
