from shohor_common.settings import *  # noqa: F401,F403
from celery.schedules import crontab
from shohor_common.settings import INSTALLED_APPS, SPECTACULAR_SETTINGS

SERVICE_NAME = "b2b"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
STATIC_URL = "/api/b2b/static/"

INSTALLED_APPS = INSTALLED_APPS + ["django.contrib.postgres", "b2b_app"]

SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "TITLE": "ShohorSathi B2b API"}

CELERY_BEAT_SCHEDULE = {
    "dispatch-contract-visits": {"task": "b2b.dispatch_tomorrow", "schedule": crontab(hour=22, minute=10)},
    "monthly-invoices": {"task": "b2b.monthly_invoices", "schedule": crontab(day_of_month=1, hour=6, minute=0)},
}
