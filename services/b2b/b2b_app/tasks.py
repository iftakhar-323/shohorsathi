from celery import shared_task

from . import logic


@shared_task(name="b2b.job.status_changed")
def job_status_changed(payload):
    logic.apply_job_status(payload)


@shared_task(name="b2b.dispatch_tomorrow")
def dispatch_tomorrow():
    return logic.dispatch_tomorrow()


@shared_task(name="b2b.monthly_invoices")
def monthly_invoices():
    return logic.monthly_invoices()
