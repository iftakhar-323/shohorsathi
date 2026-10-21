from decimal import Decimal

from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    class Kind(models.TextChoices):
        PRODUCT = "product"
        SERVICE = "service"

    kind = models.CharField(max_length=10, choices=Kind.choices)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    slug = models.SlugField(unique=True)
    name_en = models.CharField(max_length=120)
    name_bn = models.CharField(max_length=120)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name_en"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name_en


class CatalogItem(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    slug = models.SlugField(unique=True)
    name_en = models.CharField(max_length=160)
    name_bn = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    # Area ids live in the auth service. Empty means available in every area.
    area_ids = ArrayField(models.PositiveIntegerField(), default=list, blank=True)
    is_active = models.BooleanField(default=True)
    # Paid placement: listed first, with a "sponsored" label, until this time.
    sponsored_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self):
        return self.name_en


class Product(CatalogItem):
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    unit = models.CharField(max_length=32, default="pcs")
    stock = models.PositiveIntegerField(default=0)
    shop_name = models.CharField(max_length=120, blank=True)


class Service(CatalogItem):
    base_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    price_note = models.CharField(max_length=160, blank=True, help_text="e.g. 'parts charged separately'")
    duration_minutes = models.PositiveIntegerField(default=60)
    warranty_days = models.PositiveIntegerField(default=7)
    emergency_available = models.BooleanField(default=False)


class SponsoredPlacement(models.Model):
    """One paid boost of a product or service (a shop, brand or provider pays to be listed first)."""

    item_type = models.CharField(max_length=10, choices=[("product", "Product"), ("service", "Service")])
    slug = models.SlugField()
    name = models.CharField(max_length=160)
    sponsor_name = models.CharField(max_length=120)
    fee = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class GroupDeal(models.Model):
    title_en = models.CharField(max_length=160)
    title_bn = models.CharField(max_length=160)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="group_deals")
    area_ids = ArrayField(models.PositiveIntegerField(), default=list, blank=True)
    target_participants = models.PositiveIntegerField(default=3)
    current_participants = models.PositiveIntegerField(default=0)
    participant_user_ids = ArrayField(models.PositiveBigIntegerField(), default=list, blank=True)
    discount_percent = models.PositiveIntegerField(default=15)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_locked_in(self):
        return self.current_participants >= self.target_participants

    @property
    def discounted_price(self):
        factor = Decimal(100 - self.discount_percent) / Decimal(100)
        return (self.service.base_price * factor).quantize(Decimal("1.00"))

    def join(self, user_id):
        """Add a neighbour; the row lock keeps two people joining at once from overwriting each other."""
        from django.db import transaction
        from django.utils import timezone
        from rest_framework.exceptions import ValidationError

        with transaction.atomic():
            deal = GroupDeal.objects.select_for_update().get(pk=self.pk)
            if deal.expires_at <= timezone.now() or not deal.is_active:
                raise ValidationError({"deal": "This group deal has ended."})
            if user_id in deal.participant_user_ids:
                return False
            deal.participant_user_ids.append(user_id)
            deal.current_participants = len(deal.participant_user_ids)
            deal.save(update_fields=["participant_user_ids", "current_participants"])
        self.participant_user_ids, self.current_participants = deal.participant_user_ids, deal.current_participants
        return True


class SeasonalPackage(models.Model):
    class Season(models.TextChoices):
        EID = "eid", "ঈদুল ফিতর / আযহা"
        SUMMER = "summer", "গ্রীষ্মকালীন"
        MONSOON = "monsoon", "বর্ষাকালীন"
        WINTER = "winter", "শীতকালীন"
        PUJA = "puja", "দুর্গাপূজা"

    title_en = models.CharField(max_length=160)
    title_bn = models.CharField(max_length=160)
    season = models.CharField(max_length=20, choices=Season.choices, default=Season.SUMMER)
    tagline_en = models.CharField(max_length=255, blank=True)
    tagline_bn = models.CharField(max_length=255, blank=True)
    service_slugs = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    discount_percent = models.PositiveIntegerField(default=20)
    banner_image_url = models.URLField(blank=True)
    active_from = models.DateField()
    active_until = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-active_from"]
