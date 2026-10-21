from django.db import models


class ItemType(models.TextChoices):
    PRODUCT = "product"
    SERVICE = "service"


class Slot(models.TextChoices):
    MORNING = "09-11", "09:00–11:00"
    LATE_MORNING = "11-13", "11:00–13:00"
    AFTERNOON = "14-16", "14:00–16:00"
    LATE_AFTERNOON = "16-18", "16:00–18:00"
    EVENING = "18-20", "18:00–20:00"
    NIGHT = "20-22", "20:00–22:00"


class Cart(models.Model):
    user_id = models.PositiveBigIntegerField(unique=True)
    updated_at = models.DateTimeField(auto_now=True)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    item_type = models.CharField(max_length=10, choices=ItemType.choices)
    slug = models.SlugField()
    name = models.CharField(max_length=160)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("cart", "item_type", "slug")]
        ordering = ["added_at"]


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        CONFIRMED = "confirmed"
        ON_THE_WAY = "on_the_way"
        DELIVERED = "delivered"
        COMPLETED = "completed"
        CANCELLED = "cancelled"

    class PaymentMethod(models.TextChoices):
        COD = "cod"
        ONLINE = "online"
        WALLET = "wallet"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid"
        PAID = "paid"
        REFUNDED = "refunded"

    user_id = models.PositiveBigIntegerField(db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    payment_status = models.CharField(max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    points_redeemed = models.PositiveIntegerField(default=0)
    # Set when a member orders for their building/business (B2B portal); used for monthly invoices.
    organization_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    # Address snapshot: the customer's saved address may change later, the order must not.
    contact_name = models.CharField(max_length=120)
    contact_phone = models.CharField(max_length=11)
    address_line = models.CharField(max_length=255)
    area_id = models.PositiveIntegerField()
    area_name = models.CharField(max_length=120)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def number(self):
        return f"SS{self.created_at:%y%m%d}-{self.pk:05d}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    slug = models.SlugField()
    name = models.CharField(max_length=160)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        CONFIRMED = "confirmed"
        ON_THE_WAY = "on_the_way"
        WORKING = "working"
        COMPLETED = "completed"
        CANCELLED = "cancelled"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="bookings")
    user_id = models.PositiveBigIntegerField(db_index=True)
    service_slug = models.SlugField()
    service_name = models.CharField(max_length=160)
    category_slug = models.SlugField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    warranty_days = models.PositiveIntegerField(default=7)
    scheduled_date = models.DateField()
    slot = models.CharField(max_length=5, choices=Slot.choices)
    problem_description = models.TextField(blank=True)
    photo_urls = models.JSONField(default=list, blank=True)
    is_emergency = models.BooleanField(default=False)
    # "female" when the customer asked for a woman provider (cleaner, helper, beautician…)
    required_gender = models.CharField(max_length=10, blank=True)
    # Priority charge included in price for emergency bookings
    surcharge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    provider_id = models.PositiveBigIntegerField(null=True, blank=True)
    provider_name = models.CharField(max_length=120, blank=True)
    provider_phone = models.CharField(max_length=11, blank=True)
    # Shown to the provider on arrival; the customer reads it out so the right person is verified.
    arrival_code = models.CharField(max_length=4, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_date", "slot"]


class TrackingEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    booking = models.ForeignKey(Booking, null=True, blank=True, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=16)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class WarrantyClaim(models.Model):
    class Status(models.TextChoices):
        OPEN = "open"
        APPROVED = "approved"
        REJECTED = "rejected"
        RESOLVED = "resolved"

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="warranty_claims")
    user_id = models.PositiveBigIntegerField()
    description = models.TextField()
    photo_urls = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    admin_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
