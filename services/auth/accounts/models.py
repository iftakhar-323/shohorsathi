from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from shohor_common import roles

bd_phone = RegexValidator(r"^01[3-9]\d{8}$", "Enter a Bangladeshi mobile number like 01712345678.")


class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra):
        user = self.model(phone=phone, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        extra.update(role=roles.ADMIN, is_staff=True, is_superuser=True, is_phone_verified=True)
        return self.create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=11, unique=True, validators=[bd_phone])
    email = models.EmailField(blank=True)
    full_name = models.CharField(max_length=120)
    role = models.CharField(max_length=16, choices=roles.CHOICES, default=roles.CUSTOMER)
    is_phone_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"


class Area(models.Model):
    """A neighbourhood inside a city. Every location-aware record in other services refers to an area id."""

    city = models.CharField(max_length=64, default="Dhaka")
    name_en = models.CharField(max_length=120)
    name_bn = models.CharField(max_length=120)
    ward = models.CharField(max_length=16, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("city", "name_en")]
        ordering = ["city", "name_en"]

    def __str__(self):
        return f"{self.name_en}, {self.city}"


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=40, default="Home")
    area = models.ForeignKey(Area, on_delete=models.PROTECT)
    line = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]


class OtpCode(models.Model):
    class Purpose(models.TextChoices):
        REGISTER = "register"
        RESET_PASSWORD = "reset_password"

    phone = models.CharField(max_length=11, validators=[bd_phone])
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    code_hash = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["phone", "purpose", "-created_at"])]
