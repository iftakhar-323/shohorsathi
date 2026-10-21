from django.db.models import Q
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from shohor_common.permissions import IsAdminOrReadOnly, token_role
from shohor_common.roles import ADMIN

from .models import Category, Product, Service
from .serializers import CategorySerializer, ProductSerializer, ServiceSerializer


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
            qs = qs.filter(Q(name_en__icontains=q) | Q(name_bn__icontains=q) | Q(description__icontains=q))
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
        return qs


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
