from datetime import time

from django.contrib.postgres.fields import ArrayField
from django.db import models


class Provider(models.Model):
    class Type(models.TextChoices):
        ELECTRICIAN = "electrician"
        PLUMBER = "plumber"
        CLEANER = "cleaner"
        AC_TECHNICIAN = "ac_technician"
        PAINTER = "painter"
        PEST_CONTROL = "pest_control"
        HOME_CHEF = "home_chef"
        RIDER = "rider"
        HELPER = "helper"
        OTHER = "other"

    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"
        SUSPENDED = "suspended"

    user_id = models.PositiveBigIntegerField(unique=True)
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=11)
    gender = models.CharField(max_length=10, blank=True, help_text="Lets customers request a female cleaner/helper")
    provider_type = models.CharField(max_length=20, choices=Type.choices)
    # Catalog category slugs this provider can take jobs for.
    skills = ArrayField(models.SlugField(), default=list)
    # Area ids (from the auth service) the provider works in.
    area_ids = ArrayField(models.PositiveIntegerField(), default=list)
    bio = models.TextField(blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    nid_number = models.CharField(max_length=20)
    photo_url = models.CharField(max_length=500, blank=True)
    nid_front_url = models.CharField(max_length=500, blank=True)
    nid_back_url = models.CharField(max_length=500, blank=True)
    kitchen_photo_urls = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    rejection_reason = models.CharField(max_length=255, blank=True)
    is_online = models.BooleanField(default=False)
    working_days = ArrayField(models.PositiveSmallIntegerField(), default=list, help_text="0 = Monday")
    work_start = models.TimeField(default=time(9))
    work_end = models.TimeField(default=time(20))
    payout_method = models.CharField(max_length=10, choices=[("bkash", "bKash"), ("nagad", "Nagad")], blank=True)
    payout_account = models.CharField(max_length=20, blank=True)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    jobs_completed = models.PositiveIntegerField(default=0)
    jobs_on_time = models.PositiveIntegerField(default=0)
    badges = models.JSONField(default=list, blank=True)
    last_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.provider_type})"

    @property
    def trust_score(self):
        """0–100: rating (60%), punctuality (25%) and experience on the platform (15%)."""
        rating = float(self.rating_avg) / 5 if self.rating_count else 0.6
        punctual = self.jobs_on_time / self.jobs_completed if self.jobs_completed else 0.6
        volume = min(self.jobs_completed / 50, 1)
        return round(100 * (0.6 * rating + 0.25 * punctual + 0.15 * volume))


class Job(models.Model):
    class Source(models.TextChoices):
        BOOKING = "booking"
        WARRANTY = "warranty"
        CUSTOM_REQUEST = "custom_request"
        SUBSCRIPTION_VISIT = "subscription_visit"
        B2B_VISIT = "b2b_visit", "Maintenance contract visit"

    class Status(models.TextChoices):
        OPEN = "open"
        ASSIGNED = "assigned"
        ACCEPTED = "accepted"
        ON_THE_WAY = "on_the_way"
        WORKING = "working"
        COMPLETED = "completed"
        CANCELLED = "cancelled"

    source = models.CharField(max_length=20, choices=Source.choices)
    source_id = models.PositiveBigIntegerField()
    booking_id = models.PositiveBigIntegerField(null=True, blank=True)
    user_id = models.PositiveBigIntegerField()
    title = models.CharField(max_length=200)
    service_slug = models.SlugField(blank=True)
    category_slug = models.SlugField(blank=True)
    area_id = models.PositiveIntegerField()
    area_name = models.CharField(max_length=120)
    address_line = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    customer_name = models.CharField(max_length=120)
    customer_phone = models.CharField(max_length=11)
    scheduled_date = models.DateField()
    slot = models.CharField(max_length=5)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # Platform cut fixed in advance (custom request quotes); otherwise the standard commission applies.
    commission_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_emergency = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    photo_urls = models.JSONField(default=list, blank=True)
    checklist = models.JSONField(default=list, blank=True)
    before_photos = models.JSONField(default=list, blank=True)
    after_photos = models.JSONField(default=list, blank=True)
    provider_note = models.TextField(blank=True)
    preferred_provider_id = models.PositiveBigIntegerField(null=True, blank=True, help_text="provider user id")
    provider = models.ForeignKey(Provider, null=True, blank=True, on_delete=models.SET_NULL, related_name="jobs")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    accepted_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("source", "source_id")]
        ordering = ["-is_emergency", "scheduled_date", "slot"]


class JobLog(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="logs")
    status = models.CharField(max_length=12)
    note = models.CharField(max_length=255, blank=True)
    actor = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Payout(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested"
        PAID = "paid"
        REJECTED = "rejected"

    provider = models.ForeignKey(Provider, on_delete=models.PROTECT, related_name="payouts")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=10)
    account = models.CharField(max_length=20)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REQUESTED)
    reference = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Earning(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        IN_PAYOUT = "in_payout"
        PAID = "paid"

    provider = models.ForeignKey(Provider, on_delete=models.PROTECT, related_name="earnings")
    job = models.OneToOneField(Job, on_delete=models.PROTECT, related_name="earning")
    gross = models.DecimalField(max_digits=10, decimal_places=2)
    commission = models.DecimalField(max_digits=10, decimal_places=2)
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    payout = models.ForeignKey(Payout, null=True, blank=True, on_delete=models.SET_NULL, related_name="earnings")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Review(models.Model):
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name="review")
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="reviews")
    user_id = models.PositiveBigIntegerField()
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
