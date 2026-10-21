from shohor_common.settings import *  # noqa: F401,F403
from shohor_common.settings import INSTALLED_APPS, SPECTACULAR_SETTINGS, env

SERVICE_NAME = "payment"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
STATIC_URL = "/api/payment/static/"

INSTALLED_APPS = INSTALLED_APPS + ["django.contrib.postgres", "payments"]

SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "TITLE": "ShohorSathi Payment API"}

# "mock" (development: a local test checkout page) or "sslcommerz" (bKash, Nagad, cards).
PAYMENT_GATEWAY = env("PAYMENT_GATEWAY", "mock")
SSLCOMMERZ_STORE_ID = env("SSLCOMMERZ_STORE_ID", "")
SSLCOMMERZ_STORE_PASSWORD = env("SSLCOMMERZ_STORE_PASSWORD", "")
SSLCOMMERZ_SANDBOX = env("SSLCOMMERZ_SANDBOX", "1") == "1"
# Where the gateway can reach this API, and where customers land after paying.
PUBLIC_API_URL = env("PUBLIC_API_URL", "http://localhost:8088")
