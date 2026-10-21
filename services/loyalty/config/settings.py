from shohor_common.settings import *  # noqa: F401,F403
from shohor_common.settings import INSTALLED_APPS, SPECTACULAR_SETTINGS, env

SERVICE_NAME = "loyalty"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
STATIC_URL = "/api/loyalty/static/"

INSTALLED_APPS = INSTALLED_APPS + ["django.contrib.postgres", "loyalty"]

SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "TITLE": "ShohorSathi Loyalty API"}

# Points earned per ৳100 of a completed order, and what one point is worth when redeemed.
POINTS_PER_100_TAKA = int(env("POINTS_PER_100_TAKA", "1"))
POINT_VALUE_TAKA = env("POINT_VALUE_TAKA", "1")
# Points can cover at most this share of an order's subtotal.
MAX_REDEEM_PERCENT = int(env("MAX_REDEEM_PERCENT", "20"))
SUBSCRIPTION_BONUS_POINTS = int(env("SUBSCRIPTION_BONUS_POINTS", "20"))
REFERRAL_BONUS_TAKA = env("REFERRAL_BONUS_TAKA", "100")
REFERRAL_WELCOME_TAKA = env("REFERRAL_WELCOME_TAKA", "50")
MIN_TOPUP = "50"
MAX_TOPUP = "20000"
