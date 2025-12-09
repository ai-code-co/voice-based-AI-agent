# switch to Channels:

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from . import routing as project_routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voice_agent_backend.settings")

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(project_routing.websocket_urlpatterns)
        ),
    }
)
