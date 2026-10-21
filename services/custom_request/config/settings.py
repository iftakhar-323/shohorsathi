from shohor_common.settings import *  # noqa: F401,F403
from shohor_common.settings import INSTALLED_APPS, SPECTACULAR_SETTINGS, env

SERVICE_NAME = "custom_request"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
STATIC_URL = "/api/custom_request/static/"

INSTALLED_APPS = INSTALLED_APPS + ["django.contrib.postgres", "custom_requests"]

SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "TITLE": "ShohorSathi Custom_request API"}

# Share of an accepted quote the customer pays up front (held until the job is confirmed done).
CUSTOM_REQUEST_ADVANCE_PERCENT = env("CUSTOM_REQUEST_ADVANCE_PERCENT", "30")
