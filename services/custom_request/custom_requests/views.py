from django.db.models import Count
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.views import APIView
from shohor_common.internal import IsInternal
from rest_framework.decorators import action
from rest_framework.response import Response
from shohor_common.permissions import IsAdmin

from . import logic
from .models import CustomRequest
from .serializers import AdminCustomRequestSerializer, CounterSerializer, CustomRequestSerializer, QuoteSerializer

S = CustomRequest.Status


class CustomRequestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = CustomRequestSerializer

    def get_queryset(self):
        return CustomRequest.objects.filter(user_id=self.request.user.id).prefetch_related("quotes", "logs")

    def create(self, request):
        data = CustomRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        req = logic.create(request.user.id, request.auth.get("name", ""), request.auth.get("phone", ""), data.validated_data)
        return Response(CustomRequestSerializer(req).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        return Response(CustomRequestSerializer(logic.accept(self.get_object())).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        req = logic.move(self.get_object(), S.REJECTED, "Quote rejected by customer", allowed_from={S.QUOTE_SENT})
        return Response(CustomRequestSerializer(req).data)

    @action(detail=True, methods=["post"])
    def counter(self, request, pk=None):
        data = CounterSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        req = logic.counter(self.get_object(), data.validated_data["amount"], data.validated_data.get("message", ""))
        return Response(CustomRequestSerializer(req).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        req = logic.move(
            self.get_object(), S.CANCELLED, "Cancelled by customer",
            allowed_from={S.SUBMITTED, S.UNDER_REVIEW, S.QUOTE_SENT, S.COUNTERED},
        )
        return Response(CustomRequestSerializer(req).data)


class AdminCustomRequestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminCustomRequestSerializer

    def get_queryset(self):
        qs = CustomRequest.objects.prefetch_related("quotes", "logs")
        if s := self.request.query_params.get("status"):
            qs = qs.filter(status__in=s.split(","))
        return qs

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        req = self.get_object()
        req.admin_note = request.data.get("admin_note", req.admin_note)
        logic.move(req, S.UNDER_REVIEW, "Admin is reviewing", allowed_from={S.SUBMITTED})
        return Response(AdminCustomRequestSerializer(req).data)

    @action(detail=True, methods=["patch"])
    def quote(self, request, pk=None):
        data = QuoteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        req = self.get_object()
        logic.send_quote(req, dict(data.validated_data))
        return Response(AdminCustomRequestSerializer(req).data)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        reason = request.data.get("reason", "")
        if not reason:
            return Response({"reason": ["Tell the customer why."]}, status=status.HTTP_400_BAD_REQUEST)
        req = self.get_object()
        req.rejection_reason = reason
        logic.move(req, S.REJECTED, reason, allowed_from={S.SUBMITTED, S.UNDER_REVIEW, S.COUNTERED})
        return Response(AdminCustomRequestSerializer(req).data)

    @action(detail=False)
    def trends(self, request):
        """Most requested custom services: candidates to add to the regular catalog."""
        rows = (
            CustomRequest.objects.annotate(name=Lower("service_type"))
            .values("name")
            .annotate(count=Count("id"))
            .order_by("-count")[:20]
        )
        return Response(list(rows))


class AdvancePayableView(APIView):
    permission_classes = [IsInternal]
    authentication_classes = []

    def get(self, request, pk):
        req = get_object_or_404(CustomRequest, pk=pk)
        payable = req.status in (S.ACCEPTED, S.PROVIDER_ASSIGNED, S.IN_PROGRESS) and not req.advance_paid
        return Response({"user_id": req.user_id, "amount": str(req.advance_amount or 0), "payable": payable})
