from shohor_common.settings import *  # noqa: F401,F403
from shohor_common.settings import INSTALLED_APPS, SPECTACULAR_SETTINGS, env

SERVICE_NAME = "chat"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
STATIC_URL = "/api/chat/static/"

INSTALLED_APPS = INSTALLED_APPS + ["django.contrib.postgres", "chat_app"]

SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "TITLE": "ShohorSathi Chat API"}

INSTALLED_APPS = ["daphne"] + INSTALLED_APPS + ["channels"]
ASGI_APPLICATION = "config.asgi.application"
CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [env("REDIS_URL", "redis://redis:6379/1")]}},
}

MESSENGER_VERIFY_TOKEN = env("MESSENGER_VERIFY_TOKEN", "shohor-messenger-verify-token")
MESSENGER_PAGE_ACCESS_TOKEN = env("MESSENGER_PAGE_ACCESS_TOKEN", "")
MESSENGER_BACKEND = env("MESSENGER_BACKEND", "mock")
