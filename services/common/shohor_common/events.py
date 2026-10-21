"""Async events between services, carried by Celery over Redis.

`publish("booking.created", {...})` sends one Celery task per subscribed service. Each subscriber's worker listens on
its own queue (named after the service) and registers a task named "<service>.<event>", e.g. "provider.booking.created".

Events are written to the service's outbox table in the same transaction as the change (a rolled-back write never
emits an event), sent right after commit, and retried by the `shohor.relay_outbox` beat task if the broker was down.
"""
import logging

from django.conf import settings
from django.db import transaction

log = logging.getLogger(__name__)

# event -> services that consume it. Adding a consumer means adding its queue name here and a task in that service.
SUBSCRIBERS = {
    "provider.approved": ["auth", "notification"],
    # Personal data deletion: every service holding personal data redacts its copy.
    "user.deleted": ["provider", "media", "order", "subscription", "custom_request", "city", "chat", "b2b", "notification"],
    "provider.suspended": ["auth"],
    "booking.created": ["provider", "notification", "analytics"],
    "booking.cancelled": ["provider", "notification"],
    "booking.rescheduled": ["provider"],
    "order.placed": ["catalog", "notification", "analytics", "loyalty"],
    "order.status_changed": ["notification", "payment", "loyalty", "analytics"],
    "job.status_changed": ["order", "custom_request", "subscription", "b2b", "notification", "analytics"],
    "job.completed": ["analytics"],
    "custom_request.quoted": ["notification"],
    "custom_request.accepted": ["provider", "notification"],
    "custom_request.status_changed": ["notification", "payment"],
    "subscription.visit_due": ["provider"],
    "subscription.created": ["notification", "analytics", "loyalty"],
    "subscription.status_changed": ["notification", "provider", "payment"],
    "subscription.renewal_reminder": ["notification"],
    "subscription.renewed": ["notification", "analytics", "loyalty"],
    "payment.succeeded": ["order", "subscription", "custom_request", "notification", "analytics"],
    "payment.refunded": ["notification", "order"],
    "payment.failed": ["notification"],
    "chat.message": ["notification"],
    "review.created": ["provider"],
    "issue.status_changed": ["notification", "analytics"],
    "emergency.raised": ["notification"],
    "safety.sos": ["notification"],
    "loyalty.points_earned": ["notification"],
    "b2b.visit_due": ["provider"],
    "b2b.invoice_issued": ["notification"],
}

# Tests read this instead of a broker.
sent = []

_celery = None


def _app():
    global _celery
    if _celery is None:
        from celery import Celery

        _celery = Celery(broker=settings.CELERY_BROKER_URL)
    return _celery


def _send(event, payload):
    for queue in SUBSCRIBERS.get(event, []):
        _app().send_task(f"{queue}.{event}", args=[payload], queue=queue)


def deliver(row):
    """Send one outbox row; on failure keep it for the relay to retry."""
    from django.utils import timezone

    from .models import OutboxEvent

    try:
        _send(row.event, row.payload)
    except Exception as e:  # broker down: the relay retries later
        OutboxEvent.objects.filter(pk=row.pk).update(attempts=row.attempts + 1, last_error=str(e)[:255])
        log.warning("event %s not delivered yet: %s", row.event, e)
        return False
    OutboxEvent.objects.filter(pk=row.pk).update(sent_at=timezone.now(), attempts=row.attempts + 1)
    return True


def relay(limit=500, min_age_seconds=5):
    """Retry events whose first delivery failed (run every few seconds by each service's beat)."""
    from datetime import timedelta

    from django.utils import timezone

    from .models import OutboxEvent

    cutoff = timezone.now() - timedelta(seconds=min_age_seconds)
    return sum(deliver(row) for row in OutboxEvent.objects.filter(sent_at=None, created_at__lt=cutoff)[:limit])


def publish(event, payload):
    if event not in SUBSCRIBERS:
        raise ValueError(f"unknown event {event!r}; add it to shohor_common.events.SUBSCRIBERS")
    if getattr(settings, "EVENTS_CAPTURE", False):
        # Tests run inside a transaction that never commits, so record immediately.
        sent.append((event, payload))
        return
    from .models import OutboxEvent

    row = OutboxEvent.objects.create(event=event, payload=payload)
    transaction.on_commit(lambda: deliver(row))
