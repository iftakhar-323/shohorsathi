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
