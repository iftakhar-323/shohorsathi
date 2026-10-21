from celery import shared_task

from . import events


@shared_task(name="shohor.relay_outbox")
def relay_outbox():
    return events.relay()
