from celery import shared_task
from shohor_common.events import SUBSCRIBERS

from . import logic


def _register(event):
    @shared_task(name=f"notification.{event}")
    def task(payload):
        logic.handle(event, payload)

    return task


# One Celery task for every event this service subscribes to.
TASKS = {event: _register(event) for event, queues in SUBSCRIBERS.items() if "notification" in queues}
