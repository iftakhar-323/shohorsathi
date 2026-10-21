from celery import shared_task

from . import logic


@shared_task(name="order.job.status_changed")
def job_status_changed(payload):
    logic.apply_job_status(payload)


@shared_task(name="order.payment.succeeded")
def payment_succeeded(payload):
    logic.payment_succeeded(payload)


@shared_task(name="order.payment.refunded")
def payment_refunded(payload):
    logic.payment_refunded(payload)


@shared_task(name="order.user.deleted")
def user_deleted(payload):
    from .privacy import forget

    forget(payload["user_id"])
