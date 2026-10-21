from rest_framework import serializers

from .models import Addon, MealMenu, Plan, PlanPrice, StudentVerification, Subscription, Visit

SLOT = serializers.RegexField(r"^\d{2}-\d{2}$")


class PlanPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanPrice
        fields = ["id", "plan", "duration_days", "home_size", "price"]


class PlanSerializer(serializers.ModelSerializer):
    prices = PlanPriceSerializer(many=True, read_only=True)

    class Meta:
        model = Plan
        fields = [
            "id", "category", "slug", "tier", "name_bn", "name_en", "description_bn", "description_en", "includes",
            "frequency", "deep_cleans_per_30_days", "meal_types", "weekend_special", "provider_category", "sizes_apply",
            "is_active", "sort_order", "prices",
        ]


class AddonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Addon
        fields = ["id", "slug", "name_bn", "name_en", "price", "categories", "is_active"]


class QuoteSerializer(serializers.Serializer):
    plan = serializers.SlugRelatedField(slug_field="slug", queryset=Plan.objects.all())
    duration_days = serializers.ChoiceField(choices=[7, 15, 30])
    home_size = serializers.IntegerField(min_value=0, max_value=3, default=0)
    prepaid_months = serializers.ChoiceField(choices=[1, 3, 6, 12], default=1)
    addons = serializers.ListField(child=serializers.SlugField(), required=False, default=list)
    members = serializers.ListField(child=serializers.DictField(), required=False, default=list, max_length=5)


class CreateSubscriptionSerializer(QuoteSerializer):
    start_date = serializers.DateField()
    preferred_weekday = serializers.IntegerField(min_value=0, max_value=6, default=5)
    slot = SLOT
    area_id = serializers.IntegerField(min_value=1)
    area_name = serializers.CharField(max_length=120)
    address_line = serializers.CharField(max_length=255)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    diet = serializers.ChoiceField(choices=["", "bangla", "light", "protein"], default="", required=False)
    payment_method = serializers.ChoiceField(choices=["cod", "online"], default="cod")
    auto_renew = serializers.BooleanField(default=True)

    def validate_members(self, members):
        for m in members:
            if not m.get("name") or not str(m.get("phone", "")).startswith("01"):
                raise serializers.ValidationError("Each member needs a name and a mobile number.")
        return members


class VisitSerializer(serializers.ModelSerializer):
    can_change = serializers.SerializerMethodField()
    cutoff = serializers.SerializerMethodField()

    class Meta:
        model = Visit
        fields = ["id", "date", "slot", "kind", "meal_type", "value", "status", "provider_name", "rating", "feedback", "completed_at", "can_change", "cutoff"]

    def get_can_change(self, obj):
        from .logic import can_change

        return can_change(obj)

    def get_cutoff(self, obj):
        from .logic import cutoff_for

        return cutoff_for(obj.date).isoformat()


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    next_plan = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    amount_due = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    upcoming = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "id", "plan", "duration_days", "home_size", "preferred_weekday", "slot", "start_date", "end_date", "area_id",
            "area_name", "address_line", "diet", "addons", "members", "prepaid_months", "student_discount", "price",
            "credit_applied", "amount_due", "credit", "payment_method", "paid", "status", "auto_renew", "next_plan",
            "preferred_provider_name", "paused_until", "created_at", "upcoming", "stats",
        ]

    def get_upcoming(self, obj):
        from django.utils import timezone

        rows = obj.visits.filter(date__gte=timezone.localdate()).exclude(status="cancelled")[:6]
        return VisitSerializer(rows, many=True).data

    def get_stats(self, obj):
        counts = {}
        for status in obj.visits.values_list("status", flat=True):
            counts[status] = counts.get(status, 0) + 1
        return counts


class AdminSubscriptionSerializer(SubscriptionSerializer):
    class Meta(SubscriptionSerializer.Meta):
        fields = SubscriptionSerializer.Meta.fields + ["user_id", "customer_name", "customer_phone"]


class MealMenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealMenu
        fields = ["id", "date", "meal_type", "diet", "items_bn", "items_en"]


class StudentVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentVerification
        fields = ["id", "user_id", "institution", "id_card_url", "status", "note", "created_at"]
        read_only_fields = ["id", "user_id", "status", "note", "created_at"]
