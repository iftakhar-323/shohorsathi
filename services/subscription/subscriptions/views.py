from datetime import date, timedelta

from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from shohor_common.internal import IsInternal
from shohor_common.permissions import IsAdmin, IsAdminOrReadOnly

from . import logic
from .models import Addon, MealMenu, Plan, PlanPrice, StudentVerification, Subscription, Visit
from .serializers import (
    AddonSerializer,
    AdminSubscriptionSerializer,
    CreateSubscriptionSerializer,
    MealMenuSerializer,
    PlanPriceSerializer,
    PlanSerializer,
    QuoteSerializer,
    StudentVerificationSerializer,
    SubscriptionSerializer,
    VisitSerializer,
)


class PlanViewSet(viewsets.ModelViewSet):
    serializer_class = PlanSerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"
    pagination_class = None

    def get_queryset(self):
        qs = Plan.objects.prefetch_related("prices")
        if not (self.request.auth and self.request.auth.get("role") == "admin"):
            qs = qs.filter(is_active=True)
        if c := self.request.query_params.get("category"):
            qs = qs.filter(category__in=c.split(","))
        return qs


class PlanPriceViewSet(viewsets.ModelViewSet):
    serializer_class = PlanPriceSerializer
    permission_classes = [IsAdmin]
    queryset = PlanPrice.objects.all()
    pagination_class = None


class AddonViewSet(viewsets.ModelViewSet):
    serializer_class = AddonSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None

    def get_queryset(self):
        qs = Addon.objects.all()
        if c := self.request.query_params.get("category"):
            qs = [a for a in qs.filter(is_active=True) if c in a.categories]
        return qs


class QuoteView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = QuoteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        uid = request.user.id if request.user and request.user.is_authenticated else None
        q = logic.quote(v["plan"], v["duration_days"], v["home_size"], v["prepaid_months"], v["addons"], uid, len(v["members"]))
        return Response({**q, "total": str(q["total"])})


class SubscriptionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        return Subscription.objects.filter(user_id=self.request.user.id).select_related("plan").prefetch_related("plan__prices")

    def create(self, request):
        data = CreateSubscriptionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        sub = logic.create(request.user.id, request.auth.get("name", ""), request.auth.get("phone", ""), data.validated_data)
        return Response(SubscriptionSerializer(sub).data, status=status.HTTP_201_CREATED)

    @action(detail=True)
    def visits(self, request, pk=None):
        sub = self.get_object()
        qs = sub.visits.all()
        if month := request.query_params.get("from"):
            qs = qs.filter(date__gte=month)
        return Response(VisitSerializer(qs, many=True).data)

    @action(detail=True, methods=["patch"])
    def pause(self, request, pk=None):
        until = request.data.get("until")
        if not until:
            return Response({"until": ["Pick the date to resume."]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SubscriptionSerializer(logic.pause(self.get_object(), date.fromisoformat(until))).data)

    @action(detail=True, methods=["patch"])
    def resume(self, request, pk=None):
        return Response(SubscriptionSerializer(logic.resume(self.get_object())).data)

    @action(detail=True, methods=["patch"])
    def cancel(self, request, pk=None):
        return Response(SubscriptionSerializer(logic.cancel(self.get_object())).data)

    @action(detail=True, methods=["patch"], url_path="settings")
    def preferences(self, request, pk=None):
        """Auto-renew on/off, plan upgrade at the next renewal, and the delivery/visit address."""
        sub = self.get_object()
        if "auto_renew" in request.data:
            sub.auto_renew = bool(request.data["auto_renew"])
        if "next_plan" in request.data:
            slug = request.data["next_plan"]
            plan = get_object_or_404(Plan, slug=slug, is_active=True, category=sub.plan.category) if slug else None
            sub.next_plan = plan
        sub.save(update_fields=["auto_renew", "next_plan"])
        if any(k in request.data for k in ("address_line", "area_id")):
            logic.change_address(sub, {k: request.data[k] for k in ("area_id", "area_name", "address_line", "latitude", "longitude") if k in request.data})
        return Response(SubscriptionSerializer(sub).data)

    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        sub = self.get_object()
        plan = get_object_or_404(Plan, slug=request.data["plan"]) if request.data.get("plan") else None
        new = logic.renew(sub, plan)
        return Response(SubscriptionSerializer(new).data, status=status.HTTP_201_CREATED)


class VisitViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = VisitSerializer

    def get_queryset(self):
        return Visit.objects.filter(subscription__user_id=self.request.user.id).select_related("subscription__plan")

    @action(detail=True, methods=["patch"])
    def skip(self, request, pk=None):
        return Response(VisitSerializer(logic.skip(self.get_object())).data)

    @action(detail=True, methods=["patch"])
    def unskip(self, request, pk=None):
        return Response(VisitSerializer(logic.unskip(self.get_object())).data)

    @action(detail=True, methods=["post"])
    def rate(self, request, pk=None):
        rating = int(request.data.get("rating", 0))
        if not 1 <= rating <= 5:
            return Response({"rating": ["Rate from 1 to 5."]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(VisitSerializer(logic.rate(self.get_object(), rating, request.data.get("feedback", ""))).data)

    @action(detail=True, methods=["post"])
    def reclean(self, request, pk=None):
        return Response(VisitSerializer(logic.reclean(self.get_object())).data, status=status.HTTP_201_CREATED)


class MenuViewSet(viewsets.ModelViewSet):
    serializer_class = MealMenuSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None

    def get_queryset(self):
        params = self.request.query_params
        start = params.get("from") or timezone.localdate().isoformat()
        qs = MealMenu.objects.filter(date__gte=start)
        if d := params.get("diet"):
            qs = qs.filter(diet=d)
        return qs[:84]


class StudentVerificationView(generics.GenericAPIView):
    serializer_class = StudentVerificationSerializer

    def get(self, request):
        row = StudentVerification.objects.filter(user_id=request.user.id).first()
        return Response(StudentVerificationSerializer(row).data if row else None)

    def post(self, request):
        data = StudentVerificationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row, _ = StudentVerification.objects.update_or_create(
            user_id=request.user.id,
            defaults={**data.validated_data, "status": StudentVerification.Status.PENDING, "note": ""},
        )
        return Response(StudentVerificationSerializer(row).data, status=status.HTTP_201_CREATED)


class AdminSubscriptionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminSubscriptionSerializer

    def get_queryset(self):
        qs = Subscription.objects.select_related("plan").prefetch_related("plan__prices")
        params = self.request.query_params
        if s := params.get("status"):
            qs = qs.filter(status=s)
        if c := params.get("category"):
            qs = qs.filter(plan__category=c)
        return qs

    @action(detail=True)
    def visits(self, request, pk=None):
        return Response(VisitSerializer(self.get_object().visits.all(), many=True).data)


class AdminStudentViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = StudentVerificationSerializer

    def get_queryset(self):
        qs = StudentVerification.objects.order_by("-created_at")
        if s := self.request.query_params.get("status"):
            qs = qs.filter(status=s)
        return qs

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        row = self.get_object()
        decision = request.data.get("status")
        if decision not in ("approved", "rejected"):
            return Response({"status": ["approved or rejected"]}, status=status.HTTP_400_BAD_REQUEST)
        row.status, row.note = decision, request.data.get("note", "")
        row.save(update_fields=["status", "note"])
        return Response(StudentVerificationSerializer(row).data)


class AdminStatsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        active = Subscription.objects.filter(status=Subscription.Status.ACTIVE)
        return Response(
            {
                "active_by_category": dict(active.values_list("plan__category").annotate(n=Count("id"))),
                "active_total": active.count(),
                "recurring_value": str(active.aggregate(s=Sum("price"))["s"] or 0),
                "visits_tomorrow": Visit.objects.filter(date=timezone.localdate() + timedelta(days=1), status__in=["scheduled", "dispatched"]).count(),
                "students_pending": StudentVerification.objects.filter(status="pending").count(),
            }
        )


class InternalPayableView(APIView):
    permission_classes = [IsInternal]
    authentication_classes = []

    def get(self, request, pk):
        sub = get_object_or_404(Subscription, pk=pk)
        return Response({"user_id": sub.user_id, "amount": str(sub.amount_due), "payable": not sub.paid and sub.status != "cancelled"})
