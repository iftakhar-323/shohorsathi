from shohor_common.settings import *  # noqa: F401,F403
from celery.schedules import crontab
from shohor_common.settings import CELERY_BEAT_SCHEDULE, INSTALLED_APPS, SPECTACULAR_SETTINGS, env

SERVICE_NAME = "subscription"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
STATIC_URL = "/api/subscription/static/"

INSTALLED_APPS = INSTALLED_APPS + ["django.contrib.postgres", "subscriptions"]

SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "TITLE": "ShohorSathi Subscription API"}

# Skip/pause for a day closes at this hour the evening before; visits are dispatched to providers right after.
SUBSCRIPTION_CUTOFF_HOUR = int(env("SUBSCRIPTION_CUTOFF_HOUR", "22"))
# Discount (%) for paying several 30-day periods up front.
PREPAY_DISCOUNTS = {"3": 5, "6": 10, "12": 15}
STUDENT_DISCOUNT_PERCENT = env("STUDENT_DISCOUNT_PERCENT", "10")
RECLEAN_WINDOW_HOURS = 48
RENEWAL_REMINDER_DAYS = 2

CELERY_BEAT_SCHEDULE = {
    **CELERY_BEAT_SCHEDULE,
    "dispatch-tomorrow": {"task": "subscription.dispatch_tomorrow", "schedule": crontab(hour=SUBSCRIPTION_CUTOFF_HOUR, minute=5)},
    "daily-housekeeping": {"task": "subscription.daily_housekeeping", "schedule": crontab(hour=0, minute=30)},
}
