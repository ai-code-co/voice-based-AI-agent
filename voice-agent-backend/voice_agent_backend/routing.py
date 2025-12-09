

# voice_agent_backend/routing.py
from django.urls import re_path
from agent import routing as agent_routing

websocket_urlpatterns = [
    *agent_routing.websocket_urlpatterns,
]
