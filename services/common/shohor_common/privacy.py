"""Helpers for the per-service halves of data export and account deletion (see auth's accounts/privacy.py)."""
from rest_framework.response import Response
from rest_framework.views import APIView

from .internal import IsInternal

DELETED_NAME = "Deleted user"


def export_view(collect):
    """An internal view returning `collect(user_id)` for the auth service's data export."""

    class ExportView(APIView):
        permission_classes = [IsInternal]
        authentication_classes = []

        def get(self, request, user_id):
            return Response(collect(user_id))

    return ExportView.as_view()


def iso(value):
    return value.isoformat() if value else None
