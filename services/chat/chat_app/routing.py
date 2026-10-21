from django.urls import path

from .consumers import ConversationConsumer

websocket_urlpatterns = [path("api/chat/ws/<int:pk>/", ConversationConsumer.as_asgi())]
