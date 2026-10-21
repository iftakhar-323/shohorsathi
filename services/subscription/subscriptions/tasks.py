from celery import shared_task

from . import logic


@shared_task(name="subscription.job.status_changed")
def job_status_changed(payload):
    logic.apply_job_status(payload)


@shared_task(name="subscription.payment.succeeded")
def payment_succeeded(payload):
    logic.mark_paid(payload)


@shared_task(name="subscription.dispatch_tomorrow")
def dispatch_tomorrow():
    return logic.dispatch_tomorrow()


@shared_task(name="subscription.daily_housekeeping")
def daily_housekeeping():
    return logic.daily_housekeeping()
