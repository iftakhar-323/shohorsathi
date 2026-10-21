from shohor_common.settings import *  # noqa: F401,F403
from shohor_common.settings import INSTALLED_APPS, SPECTACULAR_SETTINGS, env

SERVICE_NAME = "order"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
STATIC_URL = "/api/order/static/"

INSTALLED_APPS = INSTALLED_APPS + ["django.contrib.postgres", "orders"]

SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "TITLE": "ShohorSathi Order API"}

# Flat delivery charge added to orders that contain products. Services are priced on their own.
ORDER_DELIVERY_FEE = env("ORDER_DELIVERY_FEE", "0")

# Priority charge (% of the service price) for one-tap emergency bookings.
EMERGENCY_SURCHARGE_PERCENT = env("EMERGENCY_SURCHARGE_PERCENT", "25")
POINT_VALUE_TAKA = env("POINT_VALUE_TAKA", "1")
