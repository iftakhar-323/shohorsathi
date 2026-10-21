from shohor_common.settings import *  # noqa: F401,F403
from shohor_common.settings import INSTALLED_APPS, SPECTACULAR_SETTINGS, env

SERVICE_NAME = "media"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
STATIC_URL = "/api/media/static/"

INSTALLED_APPS = INSTALLED_APPS + ["django.contrib.postgres", "files"]

SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "TITLE": "ShohorSathi Media API"}

MEDIA_ROOT = env("MEDIA_ROOT", "/data/media")
# Public files are served straight from this path by the gateway.
MEDIA_URL = "/media/"
MEDIA_MAX_BYTES = 10 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = MEDIA_MAX_BYTES
FILE_UPLOAD_PERMISSIONS = 0o644
