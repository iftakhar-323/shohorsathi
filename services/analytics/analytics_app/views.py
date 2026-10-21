from rest_framework.response import Response
from rest_framework.views import APIView
from shohor_common.permissions import IsAdmin

from . import logic


def params(request):
    days = min(max(int(request.query_params.get("days", 30)), 1), 365)
    return days, request.query_params.get("city") or None


class SummaryView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(logic.summary(*params(request)))


class HeatmapView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(logic.heatmap(*params(request)))
