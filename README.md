<!-- daphne -p 8000 voice_agent_backend.asgi:application# voice-based-ai-agent/ -->
# voice-based-AI-agent
1. Project structure (Django + Channels)

Something like:

voice_agent_backend/
  manage.py
  voice_agent_backend/
    __init__.py
    settings.py
    urls.py
    asgi.py
    routing.py
  agent/
    __init__.py
    models.py
    consumers.py
    memory.py
    realtime_bridge.py
    routing.py


We’ll have:

agent.models → user, memory, conversation models

agent.consumers → WebSocket consumer /ws/voice/

agent.memory → load and update memories (using Django ORM + OpenAI)

agent.realtime_bridge → helper that talks to OpenAI Realtime API via WebSocket

voice_agent_backend.routing → top-level Channels routing


2. Install Django + Channels + deps

In a fresh backend folder:

mkdir voice_agent_backend
cd voice_agent_backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install django channels "channels-redis" python-dotenv websockets openai


Initialize project & app:

django-admin startproject voice_agent_backend .
python manage.py startapp agent


Add a .env in project root:

OPENAI_API_KEY=sk-xxxx
OPENAI_REALTIME_MODEL=gpt-4o-realtime-preview
DJANGO_SECRET_KEY=your-secret
REDIS_URL=redis://127.0.0.1:6379/0   # for channels-redis


(You need Redis running for Channels; for dev: docker run -p 6379:6379 redis or system redis.)


1) Frontend — Vue 3 (Vite)

Responsibilities:

Capture microphone (MediaStream → AudioWorklet / ScriptProcessor)

Convert Float32 → PCM16 (Int16 little-endian) and send binary frames over WebSocket

Send control messages as JSON (start_session, stop_speaking, end_session, optional user_transcript)

Receive JSON messages (ai_text_delta) and binary audio frames

Play audio in real-time using AudioContext (PCM16 → Float32 → AudioBuffer)

Maintain client UI state: streaming text (currentTurnText), history (assistantText), connection status

Key points:

Set ws.binaryType = "arraybuffer"

Use AudioContext({ sampleRate: 16000 }) if Realtime uses 16k PCM

Implement VAD client-side or use hold-to-talk

2) Backend — Django + Channels + Daphne

Responsibilities:

Accept client WS connections (/ws/voice/?user_id=...)

Manage per-connection session state (user id, conversation session row)

Forward audio bytes to OpenAI Realtime (via backend WebSocket bridge)

Receive streaming events from Realtime, forward transcripts (JSON) and PCM audio (binary) to client

Log conversation events to DB; run memory extraction after session end

Key libraries:

channels (ASGI routing), daphne (ASGI server), channels_redis (channel layer)

DB access:

All ORM calls wrapped via database_sync_to_async(...) in async consumers

Consumer: agent.consumers.VoiceConsumer — one instance per client WS connection

3) Realtime bridge (server → OpenAI Realtime)

Responsibilities:

Create and maintain a WebSocket to OpenAI Realtime endpoint

Send session.update (instructions, input/output audio format, modalities, VAD config)

Send input_audio_buffer.append events (base64 PCM chunk) and input_audio_buffer.commit

Send response.create with instructions (repeat important constraints like language, brevity)

Listen & parse Realtime events:

input_audio_buffer.speech_started

conversation.item.*

response.created, response.content_part.added

response.audio_transcript.delta (spoken text)

response.output_audio.delta / response.audio.delta (base64 PCM)

Decode base64 to bytes and call consumer callbacks (on_text, on_audio_chunk)

Important: event names and payload shapes may vary with API versions — log all events during development.

4) Database & Memory (Django ORM: SQLite for dev, Postgres for prod)

Schemas (core tables):

UserProfile (id, display_name, created_at)

UserMemory (id, user FK, type, content, importance, timestamps)

ConversationSession (id, user FK, started_at, ended_at, title)

ConversationEvent (id, session FK, role, content, created_at)

Memory loop:

Store raw ConversationEvents during session

On end/disconnect: build transcript → call LLM (chat model) to extract memories (JSON) → insert UserMemory rows