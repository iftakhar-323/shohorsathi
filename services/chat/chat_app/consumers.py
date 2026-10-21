"""WebSocket: /api/chat/ws/<conversation_id>/?token=<access JWT>. Receive-only; messages are sent through the REST API."""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .logic import can_access
from .models import Conversation


@database_sync_to_async
def allowed(conversation_id, token):
    try:
        claims = AccessToken(token)
    except TokenError:
        return False
    conv = Conversation.objects.filter(pk=conversation_id).first()
    return bool(conv) and can_access(conv, claims["user_id"], claims.get("role"))


class ConversationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.conversation_id = int(self.scope["url_route"]["kwargs"]["pk"])
        token = parse_qs(self.scope.get("query_string", b"").decode()).get("token", [""])[0]
        if not await allowed(self.conversation_id, token):
            await self.close(code=4403)
            return
        self.group = f"conversation_{self.conversation_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def chat_message(self, event):
        await self.send_json(event["message"])
