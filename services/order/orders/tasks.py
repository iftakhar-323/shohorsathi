from celery import shared_task

from . import logic


@shared_task(name="order.job.status_changed")
def job_status_changed(payload):
    logic.apply_job_status(payload)
