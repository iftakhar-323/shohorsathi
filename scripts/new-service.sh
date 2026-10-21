#!/usr/bin/env bash
# Scaffolds a new Django service: ./scripts/new-service.sh <service> <django_app>
# Afterwards: add its database to infra/postgres/init.sql, its routes to gateway/nginx.conf,
# its containers to docker-compose.yml and its name to the CI matrix.
set -euo pipefail
cd "$(dirname "$0")/../services"

service=$1
app=$2
app_class=$(echo "$app" | sed -r "s/(^|_)([a-z])/\U\2/g")
[ -e "$service" ] && { echo "services/$service already exists"; exit 1; }

mkdir -p "$service/config" "$service/$app/migrations"
touch "$service/$app/__init__.py" "$service/$app/migrations/__init__.py"

cat > "$service/Dockerfile" <<EOF
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY common /common
RUN pip install --no-cache-dir /common

COPY $service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY $service/ .

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi -b 0.0.0.0:8000 --workers 2"]
EOF

cat > "$service/requirements.txt" <<'EOF'
gunicorn>=23,<24
pytest>=8,<9
pytest-django>=4.9,<5
EOF

cat > "$service/pytest.ini" <<'EOF'
[pytest]
DJANGO_SETTINGS_MODULE = config.settings_test
python_files = tests.py test_*.py
EOF

echo 'pytest_plugins = ["shohor_common.pytest_plugin"]' > "$service/conftest.py"

cat > "$service/manage.py" <<'EOF'
#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
EOF

cat > "$service/config/__init__.py" <<'EOF'
from .celery import app as celery_app

__all__ = ["celery_app"]
EOF

cat > "$service/config/celery.py" <<EOF
from shohor_common.celery import make_celery

app = make_celery("$service")
EOF

cat > "$service/config/settings.py" <<EOF
from shohor_common.settings import *  # noqa: F401,F403
from shohor_common.settings import INSTALLED_APPS, SPECTACULAR_SETTINGS

SERVICE_NAME = "$service"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
STATIC_URL = "/api/$service/static/"

INSTALLED_APPS = INSTALLED_APPS + ["django.contrib.postgres", "$app"]

SPECTACULAR_SETTINGS = {**SPECTACULAR_SETTINGS, "TITLE": "ShohorSathi ${service^} API"}
EOF

cat > "$service/config/settings_test.py" <<'EOF'
from shohor_common.testing import overrides

from .settings import *  # noqa: F401,F403
from .settings import SIMPLE_JWT

globals().update(overrides(SIMPLE_JWT))
EOF

cat > "$service/config/urls.py" <<EOF
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from shohor_common.health import health_urls

urlpatterns = health_urls("$service") + [
    path("api/$service/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/$service/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("", include("$app.urls")),
]
EOF

cat > "$service/config/wsgi.py" <<'EOF'
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()
EOF

cat > "$service/$app/apps.py" <<EOF
from django.apps import AppConfig


class ${app_class}Config(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "$app"
EOF

echo "services/$service created"
