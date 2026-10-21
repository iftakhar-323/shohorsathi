from django.utils import timezone
from rest_framework import serializers

from .models import CounterOffer, CustomRequest, Quote, StatusLog


class QuoteSerializer(serializers.ModelSerializer):
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    category_slug = serializers.SlugField(write_only=True, required=False)

    class Meta:
        model = Quote
        fields = [
            "id", "labor", "materials", "transport", "platform_fee", "total", "timeline_days", "provider_type", "note",
            "is_current", "created_at", "category_slug",
        ]
        read_only_fields = ["id", "is_current", "created_at"]


class CounterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CounterOffer
        fields = ["amount", "message", "created_at"]
        read_only_fields = ["created_at"]


class LogSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatusLog
        fields = ["status", "note", "created_at"]


class CustomRequestSerializer(serializers.ModelSerializer):
    quote = serializers.SerializerMethodField()
    counter = CounterSerializer(read_only=True)
    logs = LogSerializer(many=True, read_only=True)

    class Meta:
        model = CustomRequest
        fields = [
            "id", "service_type", "description", "media_urls", "area_id", "area_name", "address_line", "latitude",
            "longitude", "preferred_date", "budget_min", "budget_max", "status", "rejection_reason", "final_amount",
            "advance_amount", "advance_paid", "provider_name", "provider_phone", "quote", "counter", "logs",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "rejection_reason", "final_amount", "advance_amount", "advance_paid", "provider_name",
            "provider_phone", "created_at", "updated_at",
        ]

    def get_quote(self, obj):
        quote = obj.current_quote
        return QuoteSerializer(quote).data if quote else None

    def validate_preferred_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("Pick today or a later date.")
        return value

    def validate(self, attrs):
        low, high = attrs.get("budget_min"), attrs.get("budget_max")
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError({"budget_max": "Maximum must be at least the minimum."})
        return attrs


class AdminCustomRequestSerializer(CustomRequestSerializer):
    quotes = QuoteSerializer(many=True, read_only=True)

    class Meta(CustomRequestSerializer.Meta):
        fields = CustomRequestSerializer.Meta.fields + [
            "user_id", "customer_name", "customer_phone", "category_slug", "admin_note", "quotes",
        ]
