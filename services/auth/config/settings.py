from shohor_common.settings import *  # noqa: F401,F403
from celery.schedules import crontab
from shohor_common.settings import CELERY_BEAT_SCHEDULE, INSTALLED_APPS, REST_FRAMEWORK, SPECTACULAR_SETTINGS, env, env_bool

SERVICE_NAME = "auth"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
STATIC_URL = "/api/auth/static/"

INSTALLED_APPS = INSTALLED_APPS + ["rest_framework_simplejwt", "rest_framework_simplejwt.token_blacklist", "accounts"]
AUTH_USER_MODEL = "accounts.User"

# The auth service owns the user table, so it loads the real user instead of a stateless TokenUser.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
}

SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "TITLE": "ShohorSathi Auth API"}

OTP_DEBUG = env_bool("OTP_DEBUG")
OTP_TTL_SECONDS = 300
OTP_RESEND_SECONDS = 60
OTP_MAX_ATTEMPTS = 5
OTP_THROTTLE_RATE = env("OTP_THROTTLE_RATE", "10/hour")

# Bump when the terms or privacy notice change; users accept the current version at sign-up.
TERMS_VERSION = "2026-10"

CELERY_BEAT_SCHEDULE = {
    **CELERY_BEAT_SCHEDULE,
    # Home Profile upkeep reminders (Dhap 8), sent each morning.
    "home-reminders-due": {"task": "auth.home_reminders_due", "schedule": crontab(hour=9, minute=0)},
}
