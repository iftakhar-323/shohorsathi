from datetime import timedelta

from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone
from rest_framework import generics
from shohor_common import events
from shohor_common.permissions import IsAdmin
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from shohor_common.internal import IsInternal
from shohor_common.permissions import IsAdminOrReadOnly, token_role
from shohor_common.roles import ADMIN

from .models import Category, GroupDeal, Product, SeasonalPackage, Service, SponsoredPlacement
from .serializers import (
    CategorySerializer,
    GroupDealSerializer,
    ProductSerializer,
    SeasonalPackageSerializer,
    ServiceSerializer,
    SponsoredPlacementSerializer,
    SponsorSerializer,
)


# A filled deal can still be booked at its price this many days after it closes.
GROUP_DEAL_BOOKING_DAYS = 14


def _int_param(params, name):
    value = params.get(name)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        raise ValidationError({name: "Must be a whole number."})


class AdminSeesInactiveMixin:
    """Customers only see active rows; admins see everything so they can re-enable items."""

    def base_queryset(self):
        qs = self.queryset
        return qs if token_role(self.request) == ADMIN else qs.filter(is_active=True)


class CategoryViewSet(AdminSeesInactiveMixin, viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None
    lookup_field = "slug"

    def get_queryset(self):
        qs = self.base_queryset()
        kind = self.request.query_params.get("kind")
        return qs.filter(kind=kind) if kind else qs


class CatalogItemViewSet(AdminSeesInactiveMixin, viewsets.ModelViewSet):
    """Shared search & filter: ?q= &category=<slug> &area=<id> &min_price= &max_price= &ordering=price|-price"""

    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"
    price_field = "price"

    def get_queryset(self):
        params = self.request.query_params
        qs = self.base_queryset().select_related("category")

        if q := params.get("q", "").strip():
            exact = qs.filter(Q(name_en__icontains=q) | Q(name_bn__icontains=q) | Q(description__icontains=q))
            if exact.exists():
                qs = exact
            else:
                try:
                    from django.contrib.postgres.search import TrigramSimilarity
                    fuzzy = qs.annotate(
                        sim_bn=TrigramSimilarity("name_bn", q),
                        sim_en=TrigramSimilarity("name_en", q),
                    ).filter(Q(sim_bn__gt=0.15) | Q(sim_en__gt=0.15)).order_by("-sim_bn", "-sim_en")
                    if fuzzy.exists():
                        qs = fuzzy
                    else:
                        qs = exact
                except Exception:
                    qs = exact
        if category := params.get("category"):
            qs = qs.filter(Q(category__slug=category) | Q(category__parent__slug=category))
        if (area := _int_param(params, "area")) is not None:
            qs = qs.filter(Q(area_ids=[]) | Q(area_ids__contains=[area]))
        if (low := _int_param(params, "min_price")) is not None:
            qs = qs.filter(**{f"{self.price_field}__gte": low})
        if (high := _int_param(params, "max_price")) is not None:
            qs = qs.filter(**{f"{self.price_field}__lte": high})
        if params.get("ordering") in ("price", "-price"):
            qs = qs.order_by(params["ordering"].replace("price", self.price_field))
        else:
            # Paid placements first; within each group the usual order (relevance for a fuzzy search, newest otherwise).
            current = qs.query.order_by or qs.model._meta.ordering
            qs = qs.annotate(sponsored_now=Case(When(sponsored_until__gt=timezone.now(), then=Value(1)), default=Value(0),
                                                output_field=IntegerField())).order_by("-sponsored_now", *current)
        return qs

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def sponsor(self, request, slug=None):
        """Book a paid boost: extends the item's sponsored period and records the fee."""
        item = self.get_object()
        data = SponsorSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        now = timezone.now()
        start = max(now, item.sponsored_until or now)
        item.sponsored_until = start + timedelta(days=data.validated_data["days"])
        item.save(update_fields=["sponsored_until"])
        item_type = "service" if isinstance(item, Service) else "product"
        placement = SponsoredPlacement.objects.create(
            item_type=item_type, slug=item.slug, name=item.name_bn, sponsor_name=data.validated_data["sponsor_name"],
            fee=data.validated_data["fee"], starts_at=start, ends_at=item.sponsored_until,
        )
        events.publish("listing.sponsored", {"item_type": item_type, "slug": item.slug, "name": item.name_bn,
                                             "fee": str(placement.fee), "sponsor": placement.sponsor_name})
        return Response(SponsoredPlacementSerializer(placement).data, status=201)


class ProductViewSet(CatalogItemViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer


class ServiceViewSet(CatalogItemViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    price_field = "base_price"

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("emergency") == "1":
            qs = qs.filter(emergency_available=True)
        return qs


class GroupDealViewSet(viewsets.ModelViewSet):
    queryset = GroupDeal.objects.filter(is_active=True).select_related("service")
    serializer_class = GroupDealSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_permissions(self):
        if self.action == "join":
            from rest_framework.permissions import IsAuthenticated
            return [IsAuthenticated()]
        return [IsAdminOrReadOnly()]

    def get_queryset(self):
        from django.utils import timezone

        qs = super().get_queryset()
        if self.action != "join":
            qs = qs.filter(expires_at__gt=timezone.now())
        if area := self.request.query_params.get("area"):
            try:
                area_id = int(area)
                qs = qs.filter(Q(area_ids=[]) | Q(area_ids__contains=[area_id]))
            except ValueError:
                pass
        return qs

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        deal = self.get_object()
        user_id = request.user.id
        if not user_id:
            return Response({"detail": "Authentication required"}, status=401)
        joined = deal.join(user_id)
        return Response({
            "joined": joined,
            "current_participants": deal.current_participants,
            "target_participants": deal.target_participants,
            "is_locked_in": deal.is_locked_in,
            "deal": GroupDealSerializer(deal, context={"request": request}).data,
        })


class SeasonalPackageViewSet(viewsets.ModelViewSet):
    queryset = SeasonalPackage.objects.filter(is_active=True)
    serializer_class = SeasonalPackageSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        from django.utils import timezone

        qs = super().get_queryset()
        if token_role(self.request) != ADMIN:
            today = timezone.localdate()
            qs = qs.filter(active_from__lte=today, active_until__gte=today)
        if season := self.request.query_params.get("season"):
            qs = qs.filter(season=season)
        return qs


class GroupDealDiscountView(APIView):
    """Order service, at checkout: the best discount a customer earned from a filled group deal for this service."""

    permission_classes = [IsInternal]
    authentication_classes = []

    def get(self, request):
        from django.utils import timezone

        user_id = _int_param(request.query_params, "user_id")
        deals = GroupDeal.objects.filter(
            service__slug=request.query_params.get("slug", ""), is_active=True, participant_user_ids__contains=[user_id],
            expires_at__gt=timezone.now() - timedelta(days=GROUP_DEAL_BOOKING_DAYS),
        )
        best = max((d for d in deals if d.is_locked_in), key=lambda d: d.discount_percent, default=None)
        return Response({"deal_id": best.id, "percent": best.discount_percent} if best else {"deal_id": None, "percent": 0})


class SponsoredPlacementListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = SponsoredPlacementSerializer
    queryset = SponsoredPlacement.objects.all()
