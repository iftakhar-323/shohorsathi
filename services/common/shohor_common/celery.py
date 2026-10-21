import os

from celery import Celery


def make_celery(service_name):
    """Celery app for a service: consumes its own queue and runs its periodic jobs."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    app = Celery(service_name)
    app.config_from_object("django.conf:settings", namespace="CELERY")
    app.conf.task_default_queue = service_name
    app.autodiscover_tasks()
    return app
