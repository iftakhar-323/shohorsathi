from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Address, Area, HomeProfile, HomeReminder, OtpCode, User, bd_phone


class OtpRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(validators=[bd_phone])
    purpose = serializers.ChoiceField(choices=OtpCode.Purpose.choices)
    channel = serializers.ChoiceField(choices=["sms", "whatsapp"], default="sms", required=False)


class RegisterSerializer(serializers.Serializer):
    phone = serializers.CharField(validators=[bd_phone])
    full_name = serializers.CharField(max_length=120)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, validators=[validate_password])
    otp = serializers.CharField(min_length=6, max_length=6)
    accept_terms = serializers.BooleanField()
    marketing_opt_in = serializers.BooleanField(required=False, default=False)

    def validate_accept_terms(self, value):
        if not value:
            raise serializers.ValidationError("Please accept the terms and privacy policy.")
        return value

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("This phone number is already registered.")
        return value


class PasswordResetSerializer(serializers.Serializer):
    phone = serializers.CharField(validators=[bd_phone])
    otp = serializers.CharField(min_length=6, max_length=6)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "phone", "email", "full_name", "role", "is_phone_verified", "date_joined", "terms_version", "terms_accepted_at", "marketing_opt_in"]
        read_only_fields = ["id", "phone", "role", "is_phone_verified", "date_joined", "terms_version", "terms_accepted_at"]


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "phone", "email", "full_name", "role", "is_phone_verified", "is_active", "date_joined"]
        read_only_fields = fields


class AreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Area
        fields = ["id", "city", "name_en", "name_bn", "ward"]


class AddressSerializer(serializers.ModelSerializer):
    area_detail = AreaSerializer(source="area", read_only=True)

    class Meta:
        model = Address
        fields = ["id", "label", "area", "area_detail", "line", "latitude", "longitude", "is_default"]


class HomeReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomeReminder
        fields = [
            "id", "home", "title_en", "title_bn", "category_slug", "recommended_service_slug",
            "due_date", "frequency_days", "is_completed", "last_serviced_date", "notes", "created_at"
        ]
        read_only_fields = ["id", "home", "is_completed", "last_serviced_date", "created_at"]


class HomeProfileSerializer(serializers.ModelSerializer):
    area_detail = AreaSerializer(source="area", read_only=True)
    reminders = HomeReminderSerializer(many=True, read_only=True)
    health_score = serializers.IntegerField(read_only=True)

    class Meta:
        model = HomeProfile
        fields = [
            "id", "user", "name", "address", "area", "area_detail", "property_type",
            "square_feet", "ac_count", "refrigerator_count", "washing_machine",
            "water_purifier", "ips_inverter", "wiring_age_years", "plumbing_age_years",
            "occupancy_mode", "landlord_name", "landlord_phone", "landlord_approval_threshold",
            "health_score", "reminders", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "user", "health_score", "created_at", "updated_at"]
