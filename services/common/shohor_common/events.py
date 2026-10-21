"""Async events between services, carried by Celery over Redis.

`publish("booking.created", {...})` sends one Celery task per subscribed service. Each subscriber's worker listens on
its own queue (named after the service) and registers a task named "<service>.<event>", e.g. "provider.booking.created".

Publishing happens after the surrounding DB transaction commits, so a rolled-back write never emits an event.
"""
import logging

from django.conf import settings
from django.db import transaction

log = logging.getLogger(__name__)

# event -> services that consume it. Adding a consumer means adding its queue name here and a task in that service.
SUBSCRIBERS = {
    "provider.approved": ["auth", "notification"],
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
    "payment.succeeded": ["order", "subscription", "custom_request", "loyalty", "notification", "analytics"],
    "payment.refunded": ["notification", "order"],
    "payment.failed": ["notification"],
    "chat.message": ["notification"],
    "review.created": ["provider"],
    "issue.status_changed": ["notification", "analytics"],
    "emergency.raised": ["notification"],
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
        try:
            _app().send_task(f"{queue}.{event}", args=[payload], queue=queue)
        except Exception:  # the broker being down must not break the request that caused the event
            log.exception("could not publish %s to %s", event, queue)


def publish(event, payload):
    if event not in SUBSCRIBERS:
        raise ValueError(f"unknown event {event!r}; add it to shohor_common.events.SUBSCRIBERS")
    if getattr(settings, "EVENTS_CAPTURE", False):
        # Tests run inside a transaction that never commits, so record immediately.
        sent.append((event, payload))
        return
    transaction.on_commit(lambda: _send(event, payload))
