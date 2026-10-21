from shohor_common.settings import *  # noqa: F401,F403
from shohor_common.settings import INSTALLED_APPS, SPECTACULAR_SETTINGS, env

SERVICE_NAME = "analytics"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
STATIC_URL = "/api/analytics/static/"

INSTALLED_APPS = INSTALLED_APPS + ["django.contrib.postgres", "analytics_app"]

SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "TITLE": "ShohorSathi Analytics API"}

# Dhap 9 insights
JOBS_PER_PROVIDER_DAY = int(env("JOBS_PER_PROVIDER_DAY", "4"))
FRAUD_BIG_COD_AMOUNT = int(env("FRAUD_BIG_COD_AMOUNT", "10000"))
