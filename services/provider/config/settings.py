from shohor_common.settings import *  # noqa: F401,F403
from celery.schedules import crontab
from shohor_common.settings import CELERY_BEAT_SCHEDULE, INSTALLED_APPS, SPECTACULAR_SETTINGS, env

SERVICE_NAME = "provider"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
STATIC_URL = "/api/provider/static/"

INSTALLED_APPS = INSTALLED_APPS + ["django.contrib.postgres", "providers"]

SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "TITLE": "ShohorSathi Provider API"}

PROVIDER_COMMISSION_PERCENT = env("PROVIDER_COMMISSION_PERCENT", "15")
# Added per job for providers rated 4.8+ over at least 10 reviews.
PROVIDER_HIGH_RATING_BONUS = env("PROVIDER_HIGH_RATING_BONUS", "0")

CELERY_BEAT_SCHEDULE = {
    **CELERY_BEAT_SCHEDULE,
    "weekly-payouts": {"task": "provider.weekly_payouts", "schedule": crontab(hour=10, minute=0, day_of_week="sun")},
    "purge-rejected-documents": {"task": "provider.purge_rejected_documents", "schedule": crontab(hour=3, minute=0)},
}

# Data protection: how long a rejected applicant's NID and photos are kept (for appeals) before deletion.
REJECTED_DOCUMENT_RETENTION_DAYS = int(env("REJECTED_DOCUMENT_RETENTION_DAYS", "90"))
