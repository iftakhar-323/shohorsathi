FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY common /common
RUN pip install --no-cache-dir /common

COPY order/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY order/ .

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi -b 0.0.0.0:8000 --workers 2"]
