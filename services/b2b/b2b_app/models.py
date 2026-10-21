from django.db import models


class Organization(models.Model):
    class Kind(models.TextChoices):
        BUILDING = "building", "Apartment / building committee"
        BUSINESS = "business", "Small business / office"

    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"

    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    contact_name = models.CharField(max_length=120)
    contact_phone = models.CharField(max_length=11)
    billing_email = models.EmailField(blank=True)
    address_line = models.CharField(max_length=255)
    area_id = models.PositiveIntegerField()
    area_name = models.CharField(max_length=120)
    units = models.PositiveIntegerField(default=0, help_text="Flats or desks, for sizing contracts")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_by = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Membership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin"
        MEMBER = "member"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="members")
    user_id = models.PositiveBigIntegerField()
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=11)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        unique_together = [("organization", "user_id")]


class Contract(models.Model):
    """Annual maintenance contract: recurring visits for a fixed monthly fee."""

    class Status(models.TextChoices):
        ACTIVE = "active"
        ENDED = "ended"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="contracts")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    category_slug = models.SlugField(help_text="Provider category that does the visits")
    visits_per_month = models.PositiveSmallIntegerField(default=1)
    preferred_weekday = models.PositiveSmallIntegerField(default=5)
    slot = models.CharField(max_length=5, default="09-11")
    monthly_fee = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)


class ContractVisit(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled"
        DISPATCHED = "dispatched"
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        CANCELLED = "cancelled"

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="visits")
    date = models.DateField()
    slot = models.CharField(max_length=5)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED)
    provider_name = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["date"]


class Invoice(models.Model):
    class Status(models.TextChoices):
        ISSUED = "issued"
        PAID = "paid"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invoices")
    period_start = models.DateField()
    period_end = models.DateField()
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ISSUED)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-period_start"]
        unique_together = [("organization", "period_start")]

    @property
    def number(self):
        return f"INV-{self.organization_id:04d}-{self.period_start:%Y%m}"


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
