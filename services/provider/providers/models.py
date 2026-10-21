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
    # Told by SMS if the provider presses SOS during a job.
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_phone = models.CharField(max_length=11, blank=True)
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
    # Last approve/reject/suspend: rejected applicants' documents are purged a while after this.
    reviewed_at = models.DateTimeField(null=True, blank=True)

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
    # "female" when the customer asked for a woman provider; only matching providers see or get the job.
    required_gender = models.CharField(max_length=10, blank=True, default="")
    # The provider's rating of the customer (two-way ratings).
    customer_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    customer_feedback = models.TextField(blank=True, default="")
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
    # What is sent to the provider: earnings minus fee and insurance premium.
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    instant = models.BooleanField(default=False)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    insurance_premium = models.DecimalField(max_digits=10, decimal_places=2, default=0)
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
    class Dispute(models.TextChoices):
        NONE = ""
        OPEN = "open"
        UPHELD = "upheld", "Upheld: review hidden"
        REJECTED = "rejected"

    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name="review")
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="reviews")
    user_id = models.PositiveBigIntegerField()
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    # A provider may contest an unfair review with evidence; an upheld dispute hides it from the score.
    dispute = models.CharField(max_length=10, choices=Dispute.choices, blank=True, default="")
    dispute_reason = models.TextField(blank=True)
    dispute_note = models.CharField(max_length=255, blank=True)
    hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class CustomerScore(models.Model):
    """Providers' ratings of a customer, shown to providers before they take a job."""

    user_id = models.PositiveBigIntegerField(unique=True)
    rating_sum = models.PositiveIntegerField(default=0)
    rating_count = models.PositiveIntegerField(default=0)

    @property
    def average(self):
        return round(self.rating_sum / self.rating_count, 1) if self.rating_count else None


class SafetyIncident(models.Model):
    class Status(models.TextChoices):
        OPEN = "open"
        RESOLVED = "resolved"

    job = models.ForeignKey(Job, null=True, blank=True, on_delete=models.SET_NULL, related_name="incidents")
    raised_by = models.PositiveBigIntegerField()
    role = models.CharField(max_length=10, help_text="customer / provider")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    note = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    resolution = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "-created_at"]


class ShareLink(models.Model):
    """A customer shares a live view of a job (no phone numbers) with family."""

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="share_links")
    token = models.CharField(max_length=32, unique=True)
    created_by = models.PositiveBigIntegerField()
    expires_at = models.DateTimeField()


class InsurancePlan(models.Model):
    name_bn = models.CharField(max_length=120)
    name_en = models.CharField(max_length=120)
    partner = models.CharField(max_length=120, help_text="Insurer providing the cover")
    weekly_premium = models.DecimalField(max_digits=8, decimal_places=2)
    coverage_bn = models.TextField()
    coverage_en = models.TextField()
    is_active = models.BooleanField(default=True)


class InsuranceEnrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active"
        CANCELLED = "cancelled"

    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="insurance")
    plan = models.ForeignKey(InsurancePlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    # ISO week ("2026-W43") of the last premium taken from a payout, so a week is never charged twice.
    last_premium_week = models.CharField(max_length=8, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)


class InsuranceClaim(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted"
        FORWARDED = "forwarded", "Sent to insurer"
        PAID = "paid"
        REJECTED = "rejected"

    enrollment = models.ForeignKey(InsuranceEnrollment, on_delete=models.PROTECT, related_name="claims")
    description = models.TextField()
    photo_urls = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SUBMITTED)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class TrainingModule(models.Model):
    slug = models.SlugField(unique=True)
    title_bn = models.CharField(max_length=160)
    title_en = models.CharField(max_length=160)
    body_bn = models.TextField(blank=True)
    body_en = models.TextField(blank=True)
    video_url = models.URLField(blank=True)
    # Empty: for everyone; otherwise providers with this skill.
    category_slug = models.SlugField(blank=True)
    # [{"q": {"bn","en"}, "options": [{"bn","en"}, ...], "answer": <index>}]
    questions = models.JSONField(default=list)
    pass_percent = models.PositiveSmallIntegerField(default=70)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "slug"]


class ModuleCompletion(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="trainings")
    module = models.ForeignKey(TrainingModule, on_delete=models.CASCADE)
    score = models.PositiveSmallIntegerField()
    passed = models.BooleanField()
    certificate_code = models.CharField(max_length=16, blank=True)
    attempts = models.PositiveSmallIntegerField(default=1)
    completed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("provider", "module")]
