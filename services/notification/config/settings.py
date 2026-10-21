from shohor_common.settings import *  # noqa: F401,F403
from shohor_common.settings import INSTALLED_APPS, SPECTACULAR_SETTINGS, env

SERVICE_NAME = "notification"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
STATIC_URL = "/api/notification/static/"

INSTALLED_APPS = INSTALLED_APPS + ["django.contrib.postgres", "notifications"]

SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "TITLE": "ShohorSathi Notification API"}

# "console" logs texts (development); "http" posts to a BulkSMSBD-style gateway.
SMS_BACKEND = env("SMS_BACKEND", "console")
SMS_API_URL = env("SMS_API_URL", "")
SMS_API_KEY = env("SMS_API_KEY", "")
SMS_SENDER_ID = env("SMS_SENDER_ID", "")
