"""GET /api/<service>/health/ — process up and database reachable (used by container healthchecks and monitoring)."""
from django.db import connection
from django.urls import path
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as e:
            return Response({"status": "error", "database": str(e)[:200]}, status=503)
        return Response({"status": "ok"})


def health_urls(service):
    return [path(f"api/{service}/health/", HealthView.as_view())]
