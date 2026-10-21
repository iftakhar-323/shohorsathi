import logging

import requests
from django.conf import settings
from shohor_common import internal

from .messages import build
from .models import Broadcast, Notification, SmsLog

log = logging.getLogger(__name__)


def send_sms(phone, text):
    if not phone:
        return
    if settings.SMS_BACKEND == "http":
        try:
            res = requests.post(settings.SMS_API_URL, data={"api_key": settings.SMS_API_KEY, "senderid": settings.SMS_SENDER_ID,
                                                            "number": f"88{phone}", "message": text}, timeout=10)
            SmsLog.objects.create(phone=phone, body=text, status="sent" if res.ok else "failed", detail=res.text[:255])
        except requests.RequestException as e:
            SmsLog.objects.create(phone=phone, body=text, status="failed", detail=str(e)[:255])
    else:
        log.info("SMS to %s: %s", phone, text)
        SmsLog.objects.create(phone=phone, body=text, status="console")


def handle(event, payload):
    if event == "safety.sos":
        payload = {**payload, "admin_ids": (internal.get("auth", "/api/internal/users/", role="admin") or {}).get("ids", [])}
        for phone in payload.get("sms_phones", []):
            who = payload.get("provider_name") if payload["role"] == "provider" else payload.get("customer_name")
            send_sms(phone, f"ShohorSathi SOS: {who} pressed the emergency button at {payload.get('area_name', '')}. "
                            f"Location: https://www.openstreetmap.org/?mlat={payload.get('latitude')}&mlon={payload.get('longitude')}")
    created = []
    for note in build(event, payload):
        created.append(Notification.objects.create(
            user_id=note.user_id, kind=note.kind, title_bn=note.title_bn, title_en=note.title_en,
            body_bn=note.body_bn, body_en=note.body_en, link=note.link, app=note.app,
        ))
        if note.sms:
            user = internal.get("auth", f"/api/internal/users/{note.user_id}/")
            if user:
                send_sms(user["phone"], f"ShohorSathi: {note.title_bn}. {note.body_bn}".strip())
    return created


def broadcast(data):
    roles = {"customers": "customer", "providers": "provider", "all": "customer,provider"}[data["audience"]]
    ids = (internal.get("auth", "/api/internal/users/", role=roles) or {}).get("ids", [])
    app = "provider" if data["audience"] == "providers" else "customer"
    Notification.objects.bulk_create([
        Notification(user_id=uid, kind="promo", title_bn=data["title_bn"], title_en=data["title_en"], body_bn=data.get("body_bn", ""),
                     body_en=data.get("body_en", ""), link=data.get("link", ""), app=app)
        for uid in ids
    ])
    return Broadcast.objects.create(sent_count=len(ids), **data)
