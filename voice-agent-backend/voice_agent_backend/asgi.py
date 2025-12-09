# voice_agent_backend/asgi.py
import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# ✅ Tell Django which settings module to use
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voice_agent_backend.settings")

# ✅ This initializes Django and loads the app registry
django_asgi_app = get_asgi_application()

# ✅ Only now import anything that touches models / routing
from agent import routing as agent_routing


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(
                agent_routing.websocket_urlpatterns
            )
        ),
    }
)
