from django.core.management.base import BaseCommand
from django.db import transaction

from subscriptions.models import Addon, Plan, PlanPrice

# Development sample data from the proposal. Prices are placeholders for testing, not real rates.
CLEANING = [
    ("cleaning-basic", "basic", "বেসিক ক্লিনিং", "Basic cleaning", "monthly", 0,
     [("ঝাড়ু, মোছা, ধুলা পরিষ্কার", "Sweeping, mopping, dusting"), ("কিচেন ও বাথরুম ওয়াইপ-ডাউন", "Kitchen and bathroom wipe-down")], 1500),
    ("cleaning-standard", "standard", "স্ট্যান্ডার্ড ক্লিনিং", "Standard cleaning", "biweekly", 0,
     [("বেসিকের সবকিছু", "Everything in Basic"), ("বারান্দা, জানালা (ভেতরে)", "Balcony, windows (inside)"), ("ফ্রিজ ও কেবিনেট ওয়াইপ", "Fridge and cabinet wipe")], 2800),
    ("cleaning-premium", "premium", "প্রিমিয়াম ক্লিনিং", "Premium cleaning", "weekly", 1,
     [("মাসে ৪ ভিজিট", "4 visits a month"), ("১টি ডিপ ক্লিন: সোফা, ম্যাট্রেস, বাথরুম ডিস্কেলিং", "1 deep clean: sofa, mattress, bathroom descaling"), ("এসি ফিল্টার পরিষ্কার", "AC filter clean")], 5200),
]
MEALS = [
    ("meal-student-saver", "student_saver", "স্টুডেন্ট সেভার মিল", "Student Saver meals", ["lunch"], False, 120),
    ("meal-standard", "standard", "স্ট্যান্ডার্ড মিল", "Standard meals", ["lunch", "dinner"], True, 220),
    ("meal-premium", "premium", "প্রিমিয়াম মিল", "Premium meals", ["breakfast", "lunch", "dinner"], True, 330),
]
HOUSEHOLD = [
    ("laundry-weekly", "laundry", "লন্ড্রি ও ইস্ত্রি", "Laundry & ironing", "every_3_days", "laundry", 900),
    ("water-jar", "water", "খাবার পানির জার", "Drinking water jar", "alternate", "delivery", 600),
    ("grocery-refill", "grocery", "গ্রোসারি রিফিল", "Grocery refill", "weekly", "delivery", 300),
    ("plant-care", "plant", "গাছ ও বারান্দার যত্ন", "Plant & balcony care", "weekly", "gardening", 700),
    ("pest-preventive", "pest", "মাসিক পেস্ট কন্ট্রোল", "Monthly pest control", "monthly", "pest-control", 1200),
    ("helper-daily", "helper", "বয়স্ক/শিশু হেল্পার", "Elderly / child helper", "daily", "helper", 9000),
    ("family-tiffin", "tiffin", "পরিবারের টিফিন", "Family tiffin", "daily", "home-chef", 7500),
]
ADDONS = [
    ("sofa-wash", "সোফা ওয়াশ", "Sofa wash", 1200, ["cleaning"]),
    ("water-tank-clean", "পানির ট্যাংক পরিষ্কার", "Water tank clean", 1500, ["cleaning"]),
    ("pest-control-addon", "পেস্ট কন্ট্রোল", "Pest control", 1000, ["cleaning"]),
    ("post-tenant-deep-clean", "বাসা ছাড়ার পর ডিপ ক্লিন", "Post-tenant deep clean", 3500, ["cleaning"]),
    ("fruit-snack-box", "ফল/স্ন্যাক বক্স", "Fruit/snack box", 400, ["meal"]),
]
DURATION_FACTOR = {7: 0.3, 15: 0.55, 30: 1}
SIZE_FACTOR = {1: 1, 2: 1.4, 3: 1.8}


class Command(BaseCommand):
    help = "Seed development subscription plans, prices and add-ons (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        def price(plan, monthly, sizes):
            for days, f in DURATION_FACTOR.items():
                for size, sf in (SIZE_FACTOR.items() if sizes else [(0, 1)]):
                    PlanPrice.objects.update_or_create(plan=plan, duration_days=days, home_size=size, defaults={"price": round(monthly * f * sf)})

        for order, (slug, tier, bn, en, freq, deep, includes, monthly) in enumerate(CLEANING):
            plan, _ = Plan.objects.update_or_create(slug=slug, defaults={
                "category": "cleaning", "tier": tier, "name_bn": bn, "name_en": en, "frequency": freq,
                "deep_cleans_per_30_days": deep, "includes": [{"bn": b, "en": e} for b, e in includes],
                "provider_category": "cleaning", "sizes_apply": True, "sort_order": order,
            })
            price(plan, monthly, True)
        for order, (slug, tier, bn, en, meals, weekend, per_day) in enumerate(MEALS):
            plan, _ = Plan.objects.update_or_create(slug=slug, defaults={
                "category": "meal", "tier": tier, "name_bn": bn, "name_en": en, "frequency": "daily", "meal_types": meals,
                "weekend_special": weekend, "provider_category": "home-chef", "sort_order": order,
                "includes": [{"bn": f"দিনে {len(meals)} বেলা", "en": f"{len(meals)} meal(s) a day"}],
            })
            price(plan, per_day * 30, False)
        for order, (slug, cat, bn, en, freq, provider_cat, monthly) in enumerate(HOUSEHOLD):
            plan, _ = Plan.objects.update_or_create(slug=slug, defaults={
                "category": cat, "tier": "standard", "name_bn": bn, "name_en": en, "frequency": freq,
                "provider_category": provider_cat, "sort_order": order, "meal_types": ["lunch", "dinner"] if cat == "tiffin" else [],
            })
            price(plan, monthly, False)
        for slug, bn, en, p, cats in ADDONS:
            Addon.objects.update_or_create(slug=slug, defaults={"name_bn": bn, "name_en": en, "price": p, "categories": cats})
        self.stdout.write(self.style.SUCCESS("Subscription plans seeded."))
