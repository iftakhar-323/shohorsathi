from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Address, Area, OtpCode, User, bd_phone


class OtpRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(validators=[bd_phone])
    purpose = serializers.ChoiceField(choices=OtpCode.Purpose.choices)


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
