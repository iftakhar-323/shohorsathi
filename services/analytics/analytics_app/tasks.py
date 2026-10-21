from celery import shared_task
from shohor_common.events import SUBSCRIBERS

from . import logic


def _register(event):
    @shared_task(name=f"analytics.{event}")
    def task(payload):
        logic.record(event, payload)

    return task


TASKS = {event: _register(event) for event, queues in SUBSCRIBERS.items() if "analytics" in queues}
