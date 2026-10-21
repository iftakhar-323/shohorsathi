from rest_framework.response import Response
from rest_framework.views import APIView
from shohor_common.permissions import IsAdmin

from rest_framework import status
from shohor_common import events

from . import insights, logic


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


class ForecastView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        area = request.query_params.get("area")
        return Response(insights.forecast(request.query_params.get("city") or None, int(area) if area else None))


class ChurnView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(insights.churn(request.query_params.get("city") or None))


class WinbackView(APIView):
    """Send the chosen at-risk customers a come-back note."""

    permission_classes = [IsAdmin]

    def post(self, request):
        user_ids = [int(u) for u in request.data.get("user_ids", [])][:500]
        if not user_ids:
            return Response({"user_ids": ["Pick at least one customer."]}, status=status.HTTP_400_BAD_REQUEST)
        message = (request.data.get("message") or "").strip()[:300]
        for user_id in user_ids:
            events.publish("analytics.winback", {"user_id": user_id, "message": message})
        return Response({"sent": len(user_ids)})


class FraudView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(insights.fraud(params(request)[0]))


class RevenueView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(insights.revenue(*params(request)))
