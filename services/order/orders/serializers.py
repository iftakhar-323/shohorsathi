from rest_framework import serializers

from .models import Booking, Cart, CartItem, ItemType, Order, OrderItem, Slot, TrackingEvent, WarrantyClaim


class CartItemSerializer(serializers.ModelSerializer):
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ["id", "item_type", "slug", "name", "unit_price", "quantity", "line_total"]
        read_only_fields = ["id", "item_type", "slug", "name", "unit_price"]

    def get_line_total(self, obj):
        return str(obj.unit_price * obj.quantity)


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["items", "subtotal"]

    def get_subtotal(self, obj):
        return str(sum(i.unit_price * i.quantity for i in obj.items.all()))


class AddToCartSerializer(serializers.Serializer):
    item_type = serializers.ChoiceField(choices=ItemType.choices)
    slug = serializers.SlugField()
    quantity = serializers.IntegerField(min_value=1, max_value=99, default=1)


class ServiceDetailSerializer(serializers.Serializer):
    scheduled_date = serializers.DateField()
    slot = serializers.ChoiceField(choices=Slot.choices)
    problem_description = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    photo_urls = serializers.ListField(child=serializers.CharField(max_length=500), required=False, max_length=5)
    is_emergency = serializers.BooleanField(required=False, default=False)
    prefer_female = serializers.BooleanField(required=False, default=False)

    def validate_scheduled_date(self, value):
        from django.utils import timezone

        if value < timezone.localdate():
            raise serializers.ValidationError("Pick today or a later date.")
        return value


class CheckoutSerializer(serializers.Serializer):
    contact_name = serializers.CharField(max_length=120)
    contact_phone = serializers.RegexField(r"^01[3-9]\d{8}$")
    address_line = serializers.CharField(max_length=255)
    area_id = serializers.IntegerField(min_value=1)
    area_name = serializers.CharField(max_length=120)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)
    payment_method = serializers.ChoiceField(choices=Order.PaymentMethod.choices, default=Order.PaymentMethod.COD)
    service_details = serializers.DictField(child=ServiceDetailSerializer(), required=False, default=dict)
    redeem_points = serializers.IntegerField(min_value=0, required=False, default=0)
    organization_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["slug", "name", "unit_price", "quantity", "line_total"]


class BookingSerializer(serializers.ModelSerializer):
    slot_label = serializers.CharField(source="get_slot_display", read_only=True)
    order_number = serializers.CharField(source="order.number", read_only=True)
    warranty_until = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id", "order", "order_number", "service_slug", "service_name", "price", "scheduled_date", "slot",
            "slot_label", "problem_description", "photo_urls", "is_emergency", "surcharge", "required_gender", "status", "provider_id",
            "provider_name", "provider_phone", "arrival_code", "warranty_days", "warranty_until", "completed_at",
            "created_at",
        ]

    def to_representation(self, obj):
        data = super().to_representation(obj)
        # The provider's number is for coordinating the visit only.
        if "provider_phone" in data and obj.status not in (Booking.Status.CONFIRMED, Booking.Status.ON_THE_WAY, Booking.Status.WORKING):
            data["provider_phone"] = ""
        return data

    def get_warranty_until(self, obj):
        from datetime import timedelta

        return (obj.completed_at + timedelta(days=obj.warranty_days)).isoformat() if obj.completed_at else None


class AdminBookingSerializer(BookingSerializer):
    class Meta(BookingSerializer.Meta):
        fields = [f for f in BookingSerializer.Meta.fields if f != "arrival_code"] + ["user_id"]


class TrackingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingEvent
        fields = ["status", "note", "booking", "created_at"]


class OrderSerializer(serializers.ModelSerializer):
    number = serializers.CharField(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    bookings = BookingSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "number", "status", "payment_method", "payment_status", "subtotal", "delivery_fee", "discount", "points_redeemed", "organization_id",
            "total", "contact_name", "contact_phone", "address_line", "area_id", "area_name", "note", "items",
            "bookings", "created_at", "updated_at",
        ]


class AdminOrderSerializer(OrderSerializer):
    bookings = AdminBookingSerializer(many=True, read_only=True)

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ["user_id"]


class RescheduleSerializer(serializers.Serializer):
    scheduled_date = serializers.DateField()
    slot = serializers.ChoiceField(choices=Slot.choices)


class WarrantyClaimSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="booking.service_name", read_only=True)

    class Meta:
        model = WarrantyClaim
        fields = ["id", "booking", "service_name", "description", "photo_urls", "status", "admin_note", "created_at"]
        read_only_fields = ["id", "booking", "status", "admin_note", "created_at"]
