from celery import shared_task

from . import logic


@shared_task(name="custom_request.job.status_changed")
def job_status_changed(payload):
    logic.apply_job_status(payload)


@shared_task(name="custom_request.payment.succeeded")
def payment_succeeded(payload):
    logic.mark_advance_paid(payload)
