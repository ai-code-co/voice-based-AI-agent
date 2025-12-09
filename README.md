# voice-based-ai-agent
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