from rest_framework import serializers

from .models import Category, Product, Service


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "kind", "parent", "slug", "name_en", "name_bn", "sort_order", "is_active"]


ITEM_FIELDS = ["id", "category", "slug", "name_en", "name_bn", "description", "image_url", "area_ids", "is_active"]


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ITEM_FIELDS + ["price", "unit", "stock", "shop_name"]

    def validate_category(self, value):
        if value.kind != Category.Kind.PRODUCT:
            raise serializers.ValidationError("Category is not a product category.")
        return value


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ITEM_FIELDS + ["base_price", "price_note", "duration_minutes", "warranty_days", "emergency_available"]

    def validate_category(self, value):
        if value.kind != Category.Kind.SERVICE:
            raise serializers.ValidationError("Category is not a service category.")
        return value
