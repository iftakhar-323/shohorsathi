from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Category, Product, Service

# Development sample data only. Prices are placeholders, not real market rates.
SERVICE_CATEGORIES = [
    ("electrical", "Electrical", "ইলেকট্রিক্যাল", [
        ("electrician-visit", "Electrician visit", "ইলেকট্রিশিয়ান ভিজিট", "Fan, light, switch, wiring", 300, True),
    ]),
    ("plumbing", "Plumbing", "প্লাম্বিং", [
        ("plumber-visit", "Plumber visit", "প্লাম্বার ভিজিট", "Leak, tap, pipe, basin", 300, True),
    ]),
    ("ac", "AC service", "এসি সার্ভিস", [
        ("ac-cleaning", "AC cleaning", "এসি ক্লিনিং", "Indoor and outdoor unit wash", 800, False),
    ]),
    ("cleaning", "Cleaning", "ক্লিনিং", [
        ("home-deep-clean", "Home deep clean", "হোম ডিপ ক্লিন", "Full flat deep cleaning", 2500, False),
    ]),
    ("pest-control", "Pest control", "পেস্ট কন্ট্রোল", [
        ("cockroach-control", "Cockroach control", "তেলাপোকা নিয়ন্ত্রণ", "Gel and spray treatment", 1500, False),
    ]),
]

PRODUCT_CATEGORIES = [
    ("electrical-items", "Electrical items", "ইলেকট্রিক সামগ্রী", [
        ("led-bulb-12w", "LED bulb 12W", "এলইডি বাল্ব ১২ ওয়াট", 180, "pcs"),
    ]),
    ("cleaning-supplies", "Cleaning supplies", "ক্লিনিং সামগ্রী", [
        ("floor-cleaner-1l", "Floor cleaner 1L", "ফ্লোর ক্লিনার ১ লিটার", 220, "bottle"),
    ]),
]


class Command(BaseCommand):
    help = "Seed development categories, services and products (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        for order, (slug, en, bn, items) in enumerate(SERVICE_CATEGORIES):
            cat, _ = Category.objects.update_or_create(
                slug=slug, defaults={"kind": "service", "name_en": en, "name_bn": bn, "sort_order": order}
            )
            for s_slug, s_en, s_bn, desc, price, emergency in items:
                Service.objects.update_or_create(
                    slug=s_slug,
                    defaults={
                        "category": cat, "name_en": s_en, "name_bn": s_bn, "description": desc,
                        "base_price": price, "emergency_available": emergency,
                    },
                )
        for order, (slug, en, bn, items) in enumerate(PRODUCT_CATEGORIES):
            cat, _ = Category.objects.update_or_create(
                slug=slug, defaults={"kind": "product", "name_en": en, "name_bn": bn, "sort_order": order}
            )
            for p_slug, p_en, p_bn, price, unit in items:
                Product.objects.update_or_create(
                    slug=p_slug,
                    defaults={"category": cat, "name_en": p_en, "name_bn": p_bn, "price": price, "unit": unit, "stock": 50},
                )
        self.stdout.write(self.style.SUCCESS("Catalog seeded."))
