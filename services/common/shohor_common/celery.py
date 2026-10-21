import logging
import os

from celery import Celery, Task

log = logging.getLogger(__name__)


class RetryingTask(Task):
    """Event consumers retry with exponential backoff (5 tries) before giving up and logging the failure."""

    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    max_retries = 5

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        log.error("task %s failed for good: %s; args=%s", self.name, exc, args)


def make_celery(service_name):
    """Celery app for a service: consumes its own queue, relays its outbox and runs its periodic jobs."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    app = Celery(service_name, task_cls=RetryingTask)
    app.config_from_object("django.conf:settings", namespace="CELERY")
    app.conf.task_default_queue = service_name
    app.autodiscover_tasks()
    app.autodiscover_tasks(["shohor_common"])
    return app
