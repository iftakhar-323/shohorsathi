from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from shohor_common import events, internal

from .models import Conversation, Message

# Auto-reply for support chats: first matching keyword wins. Answers are bilingual.
FAQ = [
    (("টাকা", "পেমেন্ট", "বিকাশ", "নগদ", "pay", "bkash", "nagad"),
     "অর্ডারের সময় ক্যাশ অন ডেলিভারি বা বিকাশ/নগদ/কার্ড বাছতে পারেন। অনলাইনের টাকা কাজ শেষ হওয়া পর্যন্ত আমাদের কাছে জমা থাকে।\n\n"
     "Pay cash on delivery or bKash/Nagad/card. Online payments are held until the job is confirmed done."),
    (("রিফান্ড", "ফেরত", "refund"),
     "অর্ডার বাতিল হলে অনলাইনের টাকা নিজে থেকেই ফেরত যায়। অন্য সমস্যায় অর্ডারের পেজ থেকে রিফান্ড অনুরোধ করুন।\n\n"
     "Cancelled orders are refunded automatically. For other problems, request a refund from the order page."),
    (("ওয়ারেন্টি", "আবার", "warranty", "again"),
     "প্রতিটি কাজে ওয়ারেন্টি আছে। অর্ডারের পেজে 'ওয়ারেন্টি দাবি' চাপুন, আমরা বিনা খরচে ঠিক করে দেব।\n\n"
     "Every job has a warranty. Tap 'Warranty claim' on the order page and we'll redo it free."),
    (("বাতিল", "cancel", "সময়", "reschedule"),
     "প্রোভাইডার রওনা দেওয়ার আগ পর্যন্ত অর্ডারের পেজ থেকে বুকিং বাতিল বা সময় বদলাতে পারবেন।\n\n"
     "You can cancel or reschedule from the order page until the provider is on the way."),
]
GREETING = ("ধন্যবাদ! একজন সাপোর্ট এজেন্ট শীঘ্রই উত্তর দেবেন।\n\nThanks! A support agent will reply shortly.")


def broadcast(message):
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        f"conversation_{message.conversation_id}",
        {"type": "chat.message", "message": serialize(message)},
    )


def serialize(m):
    return {"id": m.id, "conversation": m.conversation_id, "sender_user_id": m.sender_user_id, "sender_role": m.sender_role,
            "sender_name": m.sender_name, "body": m.body, "attachment_url": m.attachment_url, "created_at": m.created_at.isoformat()}


def can_access(conv, user_id, role):
    return int(user_id) in conv.participant_ids() or (role == "admin" and conv.kind == Conversation.Kind.SUPPORT)


@transaction.atomic
def post_message(conv, user_id, role, name, body, attachment_url="", bot=False):
    if not body.strip() and not attachment_url:
        raise ValidationError({"body": "Write a message."})
    if not conv.is_open and not bot:
        raise ValidationError({"conversation": "This chat is closed."})
    msg = Message.objects.create(
        conversation=conv, sender_user_id=None if bot else user_id, sender_role="bot" if bot else role,
        sender_name="শহরসাথী" if bot else name, body=body.strip(), attachment_url=attachment_url,
    )
    conv.last_message_at = msg.created_at
    conv.save(update_fields=["last_message_at"])
    transaction.on_commit(lambda: broadcast(msg))
    if not bot:
        recipients = conv.participant_ids() - {int(user_id)}
        if role == "customer" and conv.kind == Conversation.Kind.SUPPORT:
            recipients = set()  # support agents watch the admin inbox
        for rid in recipients:
            events.publish("chat.message", {"conversation_id": conv.id, "user_id": rid, "from": name, "preview": body[:80]})
    return msg


@transaction.atomic
def open_job_chat(user_id, role, name, source, source_id):
    info = internal.get("provider", f"/api/internal/jobs/by-source/{source}/{source_id}/")
    if info is None:
        raise NotFound("Job not found.")
    if int(user_id) not in (info["customer_user_id"], info["provider_user_id"]):
        raise PermissionDenied("You are not part of this job.")
    if not info["provider_user_id"]:
        raise ValidationError({"job": "Chat opens once a provider takes the job."})
    conv, created = Conversation.objects.get_or_create(
        kind=Conversation.Kind.JOB, source=source, source_id=source_id,
        defaults={"title": info["title"], "customer_user_id": info["customer_user_id"],
                  "provider_user_id": info["provider_user_id"], "provider_name": info["provider_name"]},
    )
    if not created and conv.provider_user_id != info["provider_user_id"]:
        # the job moved to another provider: the new one takes over the chat
        conv.provider_user_id, conv.provider_name = info["provider_user_id"], info["provider_name"]
        conv.save(update_fields=["provider_user_id", "provider_name"])
    if int(user_id) == info["customer_user_id"] and not conv.customer_name:
        conv.customer_name = name
        conv.save(update_fields=["customer_name"])
    return conv


@transaction.atomic
def open_support_chat(user_id, name, subject, first_message):
    conv = Conversation.objects.create(kind=Conversation.Kind.SUPPORT, title=subject[:200] or "Support", customer_user_id=user_id, customer_name=name)
    post_message(conv, user_id, "customer", name, first_message)
    text = first_message.lower()
    answer = next((a for keys, a in FAQ if any(k in text for k in keys)), GREETING)
    post_message(conv, None, "bot", "", answer, bot=True)
    return conv


def close(conv):
    conv.is_open = False
    conv.save(update_fields=["is_open"])
    conv.last_message_at = conv.last_message_at or timezone.now()
    return conv
