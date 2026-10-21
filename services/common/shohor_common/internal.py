"""Synchronous service-to-service calls and the permission that guards internal endpoints."""
import requests
from django.conf import settings
from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission

HEADER = "X-Internal-Token"


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "A dependent service is unavailable. Please try again."


def get(service, path, **params):
    """GET another service's API. Returns parsed JSON, None on 404, raises ServiceUnavailable otherwise."""
    url = settings.SERVICE_URLS[service].rstrip("/") + path
    try:
        res = requests.get(url, params=params, headers={HEADER: settings.INTERNAL_API_TOKEN}, timeout=5)
    except requests.RequestException as e:
        raise ServiceUnavailable(f"{service} unreachable") from e
    if res.status_code == 404:
        return None
    if not res.ok:
        raise ServiceUnavailable(f"{service} answered {res.status_code}")
    return res.json()


def post(service, path, body):
    """POST to another service. Returns (status_code, json). Raises ServiceUnavailable if unreachable."""
    url = settings.SERVICE_URLS[service].rstrip("/") + path
    try:
        res = requests.post(url, json=body, headers={HEADER: settings.INTERNAL_API_TOKEN}, timeout=5)
    except requests.RequestException as e:
        raise ServiceUnavailable(f"{service} unreachable") from e
    if res.status_code >= 500:
        raise ServiceUnavailable(f"{service} answered {res.status_code}")
    return res.status_code, (res.json() if res.content else {})


class IsInternal(BasePermission):
    def has_permission(self, request, view):
        return request.headers.get(HEADER) == settings.INTERNAL_API_TOKEN
