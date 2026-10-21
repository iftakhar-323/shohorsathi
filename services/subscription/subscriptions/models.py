from django.db import models


class Plan(models.Model):
    class Category(models.TextChoices):
        CLEANING = "cleaning"
        MEAL = "meal"
        TIFFIN = "tiffin"
        LAUNDRY = "laundry"
        WATER = "water"
        GROCERY = "grocery"
        PLANT = "plant"
        PEST = "pest"
        HELPER = "helper"

    class Frequency(models.TextChoices):
        DAILY = "daily"
        ALTERNATE = "alternate", "Every other day"
        EVERY_3_DAYS = "every_3_days"
        WEEKLY = "weekly"
        BIWEEKLY = "biweekly", "Twice a month"
        MONTHLY = "monthly", "Once a month"

    category = models.CharField(max_length=10, choices=Category.choices)
    slug = models.SlugField(unique=True)
    tier = models.CharField(max_length=20, help_text="basic / standard / premium / student_saver …")
    name_bn = models.CharField(max_length=120)
    name_en = models.CharField(max_length=120)
    description_bn = models.TextField(blank=True)
    description_en = models.TextField(blank=True)
    # [{"bn": "...", "en": "..."}] shown as the plan's bullet list
    includes = models.JSONField(default=list, blank=True)
    frequency = models.CharField(max_length=14, choices=Frequency.choices)
    # Extra deep cleans per 30 days (premium cleaning).
    deep_cleans_per_30_days = models.PositiveSmallIntegerField(default=0)
    # Meals: which meals each day; one visit is created per meal.
    meal_types = models.JSONField(default=list, blank=True, help_text='e.g. ["lunch", "dinner"]')
    weekend_special = models.BooleanField(default=False)
    # Catalog category of the providers who serve this plan (cleaning, home-chef, laundry …).
    provider_category = models.SlugField()
    sizes_apply = models.BooleanField(default=False, help_text="Price depends on home size (1/2/3+ bedroom)")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["category", "sort_order"]

    def __str__(self):
        return self.name_en


class PlanPrice(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="prices")
    duration_days = models.PositiveSmallIntegerField(choices=[(7, "7 days"), (15, "15 days"), (30, "30 days")])
    # 0 when the plan's price does not depend on home size
    home_size = models.PositiveSmallIntegerField(default=0, choices=[(0, "any"), (1, "1 bedroom"), (2, "2 bedrooms"), (3, "3+ bedrooms")])
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = [("plan", "duration_days", "home_size")]
        ordering = ["duration_days", "home_size"]


class Addon(models.Model):
    slug = models.SlugField(unique=True)
    name_bn = models.CharField(max_length=120)
    name_en = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    categories = models.JSONField(default=list, help_text="Plan categories it can be added to")
    is_active = models.BooleanField(default=True)


class StudentVerification(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"

    user_id = models.PositiveBigIntegerField(unique=True)
    institution = models.CharField(max_length=160)
    id_card_url = models.CharField(max_length=500)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Subscription(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment"
        ACTIVE = "active"
        PAUSED = "paused"
        CANCELLED = "cancelled"
        EXPIRED = "expired"

    user_id = models.PositiveBigIntegerField(db_index=True)
    customer_name = models.CharField(max_length=120)
    customer_phone = models.CharField(max_length=11)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    duration_days = models.PositiveSmallIntegerField()
    home_size = models.PositiveSmallIntegerField(default=0)
    preferred_weekday = models.PositiveSmallIntegerField(default=5, help_text="0 = Monday; used by weekly/monthly plans")
    slot = models.CharField(max_length=5)
    start_date = models.DateField()
    end_date = models.DateField()
    area_id = models.PositiveIntegerField()
    area_name = models.CharField(max_length=120)
    address_line = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    diet = models.CharField(max_length=20, blank=True, help_text="meals: bangla / light / protein")
    required_gender = models.CharField(max_length=10, blank=True, help_text='"female" for a woman cleaner/helper')
    addons = models.JSONField(default=list, blank=True)
    members = models.JSONField(default=list, blank=True, help_text="mess/group plan: [{name, phone}]")
    prepaid_months = models.PositiveSmallIntegerField(default=1)
    student_discount = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    credit_applied = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Value of skipped/paused/refunded visits, applied to the next renewal.
    credit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=12, choices=[("cod", "Cash"), ("online", "Online"), ("bkash_auto", "bKash Auto-Debit")], default="cod")
    agreement_id = models.CharField(max_length=64, blank=True, default="", help_text="bKash tokenized agreement ID")
    paid = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=Status.choices)
    auto_renew = models.BooleanField(default=True)
    next_plan = models.ForeignKey(Plan, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", help_text="upgrade at renewal")
    renewed_from = models.OneToOneField("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="renewal")
    # Same-cleaner guarantee: the provider (user id) who served the first visit keeps getting this home.
    preferred_provider_id = models.PositiveBigIntegerField(null=True, blank=True)
    preferred_provider_name = models.CharField(max_length=120, blank=True)
    paused_until = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def amount_due(self):
        return max(self.price - self.credit_applied, 0)


class Visit(models.Model):
    class Kind(models.TextChoices):
        VISIT = "visit"
        DEEP_CLEAN = "deep_clean"
        RECLEAN = "reclean"
        MEAL = "meal"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled"
        SKIPPED = "skipped"
        DISPATCHED = "dispatched"
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        CANCELLED = "cancelled"

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="visits")
    date = models.DateField()
    slot = models.CharField(max_length=5)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.VISIT)
    meal_type = models.CharField(max_length=10, blank=True)
    value = models.DecimalField(max_digits=10, decimal_places=2, help_text="share of the price, credited if skipped")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED)
    provider_id = models.PositiveBigIntegerField(null=True, blank=True)
    provider_name = models.CharField(max_length=120, blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    reclean_of = models.OneToOneField("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reclean")
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["date", "slot", "meal_type"]


class MealMenu(models.Model):
    date = models.DateField()
    meal_type = models.CharField(max_length=10, choices=[("breakfast", "Breakfast"), ("lunch", "Lunch"), ("dinner", "Dinner")])
    diet = models.CharField(max_length=20, default="bangla")
    items_bn = models.CharField(max_length=255)
    items_en = models.CharField(max_length=255)

    class Meta:
        unique_together = [("date", "meal_type", "diet")]
        ordering = ["date", "meal_type"]
