from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import Category, GroupDeal, Product, SeasonalPackage, Service, SponsoredPlacement


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "kind", "parent", "slug", "name_en", "name_bn", "sort_order", "is_active"]


ITEM_FIELDS = ["id", "category", "category_slug", "slug", "name_en", "name_bn", "description", "image_url", "area_ids", "is_active",
               "is_sponsored", "sponsored_until"]


class SponsoredMixin(serializers.Serializer):
    # Uploaded photos come back from the media service as site paths (/media/public/...), not absolute URLs.
    image_url = serializers.CharField(max_length=200, required=False, allow_blank=True)
    is_sponsored = serializers.SerializerMethodField()
    sponsored_until = serializers.DateTimeField(read_only=True)

    def get_is_sponsored(self, obj):
        return bool(obj.sponsored_until and obj.sponsored_until > timezone.now())


class ProductSerializer(SponsoredMixin, serializers.ModelSerializer):
    category_slug = serializers.CharField(source="category.slug", read_only=True)

    class Meta:
        model = Product
        fields = ITEM_FIELDS + ["price", "unit", "stock", "shop_name"]

    def validate_category(self, value):
        if value.kind != Category.Kind.PRODUCT:
            raise serializers.ValidationError("Category is not a product category.")
        return value


class ServiceSerializer(SponsoredMixin, serializers.ModelSerializer):
    category_slug = serializers.CharField(source="category.slug", read_only=True)

    class Meta:
        model = Service
        fields = ITEM_FIELDS + ["base_price", "price_note", "duration_minutes", "warranty_days", "emergency_available"]

    def validate_category(self, value):
        if value.kind != Category.Kind.SERVICE:
            raise serializers.ValidationError("Category is not a service category.")
        return value


class GroupDealSerializer(serializers.ModelSerializer):
    service_slug = serializers.CharField(source="service.slug", read_only=True)
    service_name_bn = serializers.CharField(source="service.name_bn", read_only=True)
    service_name_en = serializers.CharField(source="service.name_en", read_only=True)
    base_price = serializers.DecimalField(source="service.base_price", max_digits=10, decimal_places=2, read_only=True)
    discounted_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_locked_in = serializers.BooleanField(read_only=True)
    joined = serializers.SerializerMethodField()

    class Meta:
        model = GroupDeal
        fields = [
            "id", "title_en", "title_bn", "service", "service_slug", "service_name_bn", "service_name_en",
            "base_price", "discounted_price", "area_ids", "target_participants", "current_participants",
            "discount_percent", "expires_at", "is_active", "is_locked_in", "joined", "created_at"
        ]
        read_only_fields = ["current_participants"]

    def get_joined(self, obj):
        """Whether the viewer is in; the other neighbours' ids stay private."""
        request = self.context.get("request")
        return bool(request and request.user and request.user.id in obj.participant_user_ids)


class SeasonalPackageSerializer(serializers.ModelSerializer):
    banner_image_url = serializers.CharField(max_length=200, required=False, allow_blank=True)

    class Meta:
        model = SeasonalPackage
        fields = [
            "id", "title_en", "title_bn", "season", "tagline_en", "tagline_bn",
            "service_slugs", "discount_percent", "banner_image_url", "active_from",
            "active_until", "is_active", "created_at"
        ]


class SponsorSerializer(serializers.Serializer):
    days = serializers.IntegerField(min_value=1, max_value=90)
    fee = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"))
    sponsor_name = serializers.CharField(max_length=120)


class SponsoredPlacementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SponsoredPlacement
        fields = ["id", "item_type", "slug", "name", "sponsor_name", "fee", "starts_at", "ends_at", "created_at"]
