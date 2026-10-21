from django.db import models


class CustomRequest(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted"
        UNDER_REVIEW = "under_review"
        QUOTE_SENT = "quote_sent"
        COUNTERED = "countered"
        ACCEPTED = "accepted"
        PROVIDER_ASSIGNED = "provider_assigned"
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        REJECTED = "rejected"
        CANCELLED = "cancelled"

    user_id = models.PositiveBigIntegerField(db_index=True)
    customer_name = models.CharField(max_length=120)
    customer_phone = models.CharField(max_length=11)
    service_type = models.CharField(max_length=120)
    description = models.TextField()
    media_urls = models.JSONField(default=list, blank=True)
    area_id = models.PositiveIntegerField()
    area_name = models.CharField(max_length=120)
    address_line = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    preferred_date = models.DateField()
    budget_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    category_slug = models.SlugField(blank=True, help_text="Set by admin: which providers can take it")
    admin_note = models.TextField(blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    advance_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    advance_paid = models.BooleanField(default=False)
    provider_id = models.PositiveBigIntegerField(null=True, blank=True)
    provider_name = models.CharField(max_length=120, blank=True)
    provider_phone = models.CharField(max_length=11, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def current_quote(self):
        return self.quotes.filter(is_current=True).first()


class Quote(models.Model):
    request = models.ForeignKey(CustomRequest, on_delete=models.CASCADE, related_name="quotes")
    labor = models.DecimalField(max_digits=10, decimal_places=2)
    materials = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    transport = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    timeline_days = models.PositiveIntegerField(default=1)
    provider_type = models.CharField(max_length=40, blank=True)
    note = models.TextField(blank=True)
    is_current = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def total(self):
        return self.labor + self.materials + self.transport + self.platform_fee


class CounterOffer(models.Model):
    request = models.OneToOneField(CustomRequest, on_delete=models.CASCADE, related_name="counter")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class StatusLog(models.Model):
    request = models.ForeignKey(CustomRequest, on_delete=models.CASCADE, related_name="logs")
    status = models.CharField(max_length=20)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
