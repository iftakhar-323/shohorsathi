from datetime import timedelta
from decimal import Decimal

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
    # Consent record (Personal Data Protection Ordinance): which terms/privacy notice version, and when.
    terms_version = models.CharField(max_length=20, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    marketing_opt_in = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

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


class HomeProfile(models.Model):
    class PropertyType(models.TextChoices):
        APARTMENT = "apartment", "ফ্ল্যাট / অ্যাপার্টমেন্ট"
        HOUSE = "house", "বাড়ি / ডুপ্লেক্স"
        OFFICE = "office", "অফিস / বাণিজ্যিক"

    class OccupancyMode(models.TextChoices):
        OWNER = "owner", "বাড়ির মালিক"
        TENANT = "tenant", "ভাড়াটিয়া"
        LANDLORD = "landlord", "বাড়িওয়ালা (রেন্টাল)"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="home_profiles")
    name = models.CharField(max_length=120, default="আমার বাসা")
    address = models.CharField(max_length=255)
    area = models.ForeignKey(Area, null=True, blank=True, on_delete=models.SET_NULL)
    property_type = models.CharField(max_length=20, choices=PropertyType.choices, default=PropertyType.APARTMENT)
    square_feet = models.PositiveIntegerField(default=1200)
    ac_count = models.PositiveIntegerField(default=2)
    refrigerator_count = models.PositiveIntegerField(default=1)
    washing_machine = models.BooleanField(default=True)
    water_purifier = models.BooleanField(default=True)
    ips_inverter = models.BooleanField(default=False)
    wiring_age_years = models.PositiveIntegerField(default=3)
    plumbing_age_years = models.PositiveIntegerField(default=3)
    occupancy_mode = models.CharField(max_length=20, choices=OccupancyMode.choices, default=OccupancyMode.OWNER)
    landlord_name = models.CharField(max_length=120, blank=True)
    landlord_phone = models.CharField(max_length=15, blank=True)
    landlord_approval_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1500.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def health_score(self):
        score = 100
        if self.wiring_age_years > 10:
            score -= 15
        elif self.wiring_age_years > 5:
            score -= 5
        if self.plumbing_age_years > 10:
            score -= 15
        elif self.plumbing_age_years > 5:
            score -= 5
        if self.ac_count >= 3:
            score -= 5
        overdue_count = self.reminders.filter(is_completed=False, due_date__lt=timezone.localdate()).count()
        score -= (overdue_count * 10)
        return max(20, min(100, score))


class HomeReminder(models.Model):
    home = models.ForeignKey(HomeProfile, on_delete=models.CASCADE, related_name="reminders")
    title_en = models.CharField(max_length=160)
    title_bn = models.CharField(max_length=160)
    category_slug = models.CharField(max_length=60, default="ac")
    recommended_service_slug = models.CharField(max_length=100, default="ac-cleaning")
    due_date = models.DateField()
    frequency_days = models.PositiveIntegerField(default=180)
    is_completed = models.BooleanField(default=False)
    last_serviced_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    notified_on = models.DateField(null=True, blank=True, help_text="when the due-soon reminder was sent")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date"]

    def complete(self):
        """Mark it done and schedule the next one, so recurring upkeep keeps coming back."""
        today = timezone.localdate()
        self.is_completed, self.last_serviced_date = True, today
        self.save(update_fields=["is_completed", "last_serviced_date"])
        if self.frequency_days:
            HomeReminder.objects.create(
                home=self.home, title_en=self.title_en, title_bn=self.title_bn, category_slug=self.category_slug,
                recommended_service_slug=self.recommended_service_slug, frequency_days=self.frequency_days,
                due_date=today + timedelta(days=self.frequency_days), notes=self.notes,
            )
