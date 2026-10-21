from celery import shared_task

from . import logic


@shared_task(name="provider.booking.created")
def booking_created(payload):
    logic.create_job(payload)


@shared_task(name="provider.booking.cancelled")
def booking_cancelled(payload):
    logic.cancel_from_source(payload)


@shared_task(name="provider.booking.rescheduled")
def booking_rescheduled(payload):
    logic.reschedule_from_source(payload)


@shared_task(name="provider.custom_request.accepted")
def custom_request_accepted(payload):
    logic.create_job({**payload, "source": "custom_request", "source_id": payload["request_id"]})


@shared_task(name="provider.subscription.visit_due")
def subscription_visit_due(payload):
    logic.create_job({**payload, "source": "subscription_visit", "source_id": payload["visit_id"]})


@shared_task(name="provider.subscription.status_changed")
def subscription_status_changed(payload):
    if payload["status"] in ("cancelled", "paused"):
        for visit_id in payload.get("cancelled_visit_ids", []):
            logic.cancel_from_source({"source": "subscription_visit", "source_id": visit_id})


@shared_task(name="provider.review.created")
def review_created(payload):
    logic.apply_review(payload)


@shared_task(name="provider.weekly_payouts")
def weekly_payouts():
    return logic.weekly_payouts()
