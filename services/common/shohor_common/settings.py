"""Base Django settings shared by every service. A service's settings module does
`from shohor_common.settings import *` and then sets ROOT_URLCONF, SERVICE_NAME and adds its own apps.
"""
import os
from datetime import timedelta
from pathlib import Path


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, "1" if default else "0").lower() in ("1", "true", "yes")


def read_key(path_env):
    path = env(path_env)
    return Path(path).read_text() if path else None


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-key")
DEBUG = env_bool("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "shohor_common",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER", "shohor"),
        "PASSWORD": env("POSTGRES_PASSWORD", ""),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True
STATIC_ROOT = "/app/staticfiles"

CORS_ALLOWED_ORIGINS = [o for o in env("CORS_ALLOWED_ORIGINS", "").split(",") if o]

# Services other than auth have no user table: they trust the signed token.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTStatelessUserAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle", "rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": env("THROTTLE_ANON", "120/min"), "user": env("THROTTLE_USER", "600/min")},
}

# Shared cache (rate limits are counted across all of a service's processes).
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": env("REDIS_CACHE_URL", "redis://redis:6379/2")}}

SIMPLE_JWT = {
    "ALGORITHM": "RS256",
    "SIGNING_KEY": read_key("JWT_PRIVATE_KEY_PATH"),
    "VERIFYING_KEY": read_key("JWT_PUBLIC_KEY_PATH"),
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ShohorSathi API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Event bus (see shohor_common.events) and background jobs.
CELERY_BROKER_URL = env("REDIS_URL", "redis://redis:6379/0")
CELERY_TASK_ACKS_LATE = True
CELERY_TIMEZONE = "Asia/Dhaka"
EVENTS_CAPTURE = False
# Every service relays its outbox; services add their own jobs with {**CELERY_BEAT_SCHEDULE, ...}.
CELERY_BEAT_SCHEDULE = {"relay-outbox": {"task": "shohor.relay_outbox", "schedule": 10.0}}

# Where customers open the web app; used in links sent by SMS and redirects.
CUSTOMER_WEB_URL = env("CUSTOMER_WEB_URL", "http://localhost:5173").rstrip("/")

# Internal service addresses, used for the few synchronous calls between services.
SERVICE_URLS = {
    "auth": env("AUTH_URL", "http://auth:8000"),
    "catalog": env("CATALOG_URL", "http://catalog:8000"),
    "provider": env("PROVIDER_URL", "http://provider:8000"),
    "order": env("ORDER_URL", "http://order:8000"),
    "subscription": env("SUBSCRIPTION_URL", "http://subscription:8000"),
    "custom_request": env("CUSTOM_REQUEST_URL", "http://custom-request:8000"),
    "chat": env("CHAT_URL", "http://chat:8000"),
    "loyalty": env("LOYALTY_URL", "http://loyalty:8000"),
    "b2b": env("B2B_URL", "http://b2b:8000"),
    "city": env("CITY_URL", "http://city:8000"),
    "media": env("MEDIA_URL_INTERNAL", "http://media:8000"),
    "notification": env("NOTIFICATION_URL", "http://notification:8000"),
    "payment": env("PAYMENT_URL", "http://payment:8000"),
}
# Shared secret for service-to-service calls that are not made on behalf of a user.
INTERNAL_API_TOKEN = env("INTERNAL_API_TOKEN", "dev-internal-token")

# Production hardening, active when DJANGO_DEBUG=0.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    CSRF_TRUSTED_ORIGINS = [o for o in env("CSRF_TRUSTED_ORIGINS", "").split(",") if o]

# Error tracking: set SENTRY_DSN to report exceptions from web processes and Celery workers.
if env("SENTRY_DSN"):
    import sentry_sdk

    sentry_sdk.init(dsn=env("SENTRY_DSN"), environment=env("SENTRY_ENVIRONMENT", "production"),
                    traces_sample_rate=float(env("SENTRY_TRACES_RATE", "0.05")), send_default_pii=False)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
