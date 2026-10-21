from django.db.models import Count, F, Max, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from shohor_common.permissions import IsAdmin, token_role

from . import bot, logic
from .models import Conversation, ReadState


class ConversationSerializer(serializers.ModelSerializer):
    unread = serializers.IntegerField(read_only=True, default=0)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "kind", "source", "source_id", "title", "customer_user_id", "customer_name", "provider_user_id",
                  "provider_name", "is_open", "last_message_at", "created_at", "unread", "last_message"]

    def get_last_message(self, obj):
        m = obj.messages.last()
        return m.body[:100] if m else ""


def annotate_unread(qs, user_id):
    """Messages from others newer than what this user last read."""
    last_read = ReadState.objects.filter(conversation=OuterRef("pk"), user_id=user_id).values("last_read_id")[:1]
    qs = qs.annotate(read_upto=Coalesce(Subquery(last_read), 0))
    others = Q(messages__id__gt=F("read_upto")) & ~Q(messages__sender_user_id=user_id)
    return qs.annotate(unread=Count("messages", filter=others))


def me(request):
    return int(request.user.id), token_role(request), request.auth.get("name", "")


class ConversationsView(APIView):
    def get(self, request):
        uid, role, _ = me(request)
        qs = Conversation.objects.filter(Q(customer_user_id=uid) | Q(provider_user_id=uid))
        return Response(ConversationSerializer(annotate_unread(qs, uid), many=True).data)

    def post(self, request):
        uid, role, name = me(request)
        if request.data.get("kind") == "support":
            conv = logic.open_support_chat(uid, name, request.data.get("subject", ""), request.data.get("body", ""))
        else:
            conv = logic.open_job_chat(uid, role, name, request.data.get("source", ""), int(request.data.get("source_id", 0)))
        return Response(ConversationSerializer(conv).data, status=status.HTTP_201_CREATED)


def get_conversation(request, pk):
    uid, role, _ = me(request)
    conv = get_object_or_404(Conversation, pk=pk)
    if not logic.can_access(conv, uid, role):
        raise NotFound()
    return conv


class MessagesView(APIView):
    def get(self, request, pk):
        conv = get_conversation(request, pk)
        qs = conv.messages.all()
        if after := request.query_params.get("after"):
            qs = qs.filter(id__gt=after)
        rows = list(qs[:200])
        if rows:
            ReadState.objects.update_or_create(conversation=conv, user_id=request.user.id, defaults={"last_read_id": rows[-1].id})
        return Response({"conversation": ConversationSerializer(conv).data, "messages": [logic.serialize(m) for m in rows]})

    def post(self, request, pk):
        conv = get_conversation(request, pk)
        uid, role, name = me(request)
        if role != "admin":
            role = "provider" if uid == conv.provider_user_id else "customer"
        msg = logic.post_message(conv, uid, role, name, request.data.get("body", ""), request.data.get("attachment_url", ""))
        return Response(logic.serialize(msg), status=status.HTTP_201_CREATED)


class UnreadView(APIView):
    def get(self, request):
        uid, _, _ = me(request)
        qs = annotate_unread(Conversation.objects.filter(Q(customer_user_id=uid) | Q(provider_user_id=uid)), uid)
        return Response({"unread": sum(c.unread for c in qs)})


class AdminSupportView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        qs = Conversation.objects.filter(kind=Conversation.Kind.SUPPORT)
        if request.query_params.get("open") == "1":
            qs = qs.filter(is_open=True)
        qs = qs.annotate(last_customer=Max("messages__created_at", filter=Q(messages__sender_role="customer")))
        return Response(ConversationSerializer(qs, many=True).data)


class AdminCloseView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        conv = get_object_or_404(Conversation, pk=pk, kind=Conversation.Kind.SUPPORT)
        return Response(ConversationSerializer(logic.close(conv)).data)


class MessengerWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")
        res = bot.verify_webhook(mode, token, challenge)
        if res is not None:
            return HttpResponse(res)
        return HttpResponse("Verification failed", status=403)

    def post(self, request):
        data = request.data or {}
        entries = data.get("entry", [])
        for entry in entries:
            messaging = entry.get("messaging", [])
            for msg_item in messaging:
                sender_id = msg_item.get("sender", {}).get("id")
                if not sender_id:
                    continue
                postback = msg_item.get("postback", {})
                payload = postback.get("payload")
                text = ""
                if "message" in msg_item:
                    msg_obj = msg_item["message"]
                    text = msg_obj.get("text", "")
                    quick_reply = msg_obj.get("quick_reply", {})
                    payload = payload or quick_reply.get("payload")

                reply = bot.handle_message(sender_id, text=text, payload=payload)
                bot.send_reply(sender_id, reply)

        return Response({"status": "EVENT_RECEIVED"}, status=status.HTTP_200_OK)

