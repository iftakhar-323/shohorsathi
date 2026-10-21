from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Category, Product, Service

# Development / demo sample data. Prices are placeholders, not real market rates.
# Images live in demo/images and are copied to the media volume by scripts/seed_demo.py.
IMG = "/media/public/demo"

SERVICE_CATEGORIES = [
    ("electrical", "Electrical", "ইলেকট্রিক্যাল", [
        ("electrician-visit", "Electrician visit", "ইলেকট্রিশিয়ান ভিজিট", "Fan, light, switch, socket and wiring problems",
         "ফ্যান, লাইট, সুইচ, সকেট ও ওয়্যারিংয়ের সমস্যা", 300, True, 60),
        ("ceiling-fan-installation", "Ceiling fan installation", "সিলিং ফ্যান লাগানো", "Fit or replace a ceiling fan with regulator",
         "রেগুলেটরসহ সিলিং ফ্যান লাগানো বা বদলানো", 450, False, 60),
    ]),
    ("plumbing", "Plumbing", "প্লাম্বিং", [
        ("plumber-visit", "Plumber visit", "প্লাম্বার ভিজিট", "Leaks, taps, pipes and commode problems",
         "লিকেজ, কল, পাইপ ও কমোডের সমস্যা", 300, True, 60),
        ("basin-sink-repair", "Basin & sink repair", "বেসিন ও সিংক মেরামত", "Blocked or leaking basin, kitchen sink",
         "বেসিন বা কিচেন সিংক বন্ধ বা লিক হলে", 400, False, 60),
    ]),
    ("ac", "AC service", "এসি সার্ভিস", [
        ("ac-cleaning", "AC cleaning", "এসি ক্লিনিং", "Jet wash of indoor and outdoor unit",
         "ইনডোর ও আউটডোর ইউনিট জেট ওয়াশ", 800, False, 90),
        ("ac-gas-refill", "AC gas refill", "এসি গ্যাস রিফিল", "Leak check and gas top-up for split AC",
         "স্প্লিট এসির লিক চেক ও গ্যাস ভরা", 2500, False, 90),
    ]),
    ("cleaning", "Cleaning", "ক্লিনিং", [
        ("home-deep-clean", "Home deep clean", "হোম ডিপ ক্লিন", "Full flat deep cleaning, floors, bathrooms, kitchen",
         "পুরো ফ্ল্যাট: মেঝে, বাথরুম, রান্নাঘর", 2500, False, 240),
        ("sofa-carpet-cleaning", "Sofa & carpet cleaning", "সোফা ও কার্পেট ক্লিনিং", "Shampoo and vacuum for sofa sets and carpets",
         "সোফা ও কার্পেট শ্যাম্পু ও ভ্যাকুয়াম", 1200, False, 120),
        ("kitchen-deep-clean", "Kitchen deep clean", "কিচেন ডিপ ক্লিন", "Degreasing of cabinets, hood, tiles and sink",
         "কেবিনেট, হুড, টাইলস ও সিংকের তেল-ময়লা পরিষ্কার", 1500, False, 150),
    ]),
    ("pest-control", "Pest control", "পেস্ট কন্ট্রোল", [
        ("cockroach-control", "Cockroach control", "তেলাপোকা নিয়ন্ত্রণ", "Gel and spray treatment, 30-day guarantee",
         "জেল ও স্প্রে ট্রিটমেন্ট, ৩০ দিনের গ্যারান্টি", 1500, False, 60),
        ("mosquito-fogging", "Mosquito fogging", "মশা নিধন ফগিং", "Fogging for flats and building premises",
         "ফ্ল্যাট ও বিল্ডিং চত্বরে ফগিং", 1000, False, 45),
    ]),
    ("painting", "Painting", "রং করা", [
        ("wall-painting", "Wall painting", "দেয়াল রং করা", "Per room, paint and putty included",
         "প্রতি রুম, রং ও পুটিসহ", 3500, False, 480),
    ]),
    ("appliance", "Appliance repair", "যন্ত্রপাতি মেরামত", [
        ("appliance-repair", "Fridge & washing machine repair", "ফ্রিজ ও ওয়াশিং মেশিন মেরামত", "Diagnosis at home, parts charged separately",
         "বাসায় এসে সমস্যা নির্ণয়, যন্ত্রাংশের দাম আলাদা", 500, False, 60),
    ]),
    ("moving", "House shifting", "বাসা বদল", [
        ("house-shifting", "House shifting", "বাসা বদল", "Packing, loading and a covered van inside the city",
         "প্যাকিং, লোডিং ও শহরের ভেতরে কাভার্ড ভ্যান", 6000, False, 360),
    ]),
]

PRODUCT_CATEGORIES = [
    ("electrical-items", "Electrical items", "ইলেকট্রিক সামগ্রী", [
        ("led-bulb-12w", "LED bulb 12W", "এলইডি বাল্ব ১২ ওয়াট", 180, "pcs", "Walton Plaza"),
        ("extension-board-4", "Extension board, 4 sockets", "এক্সটেনশন বোর্ড, ৪ সকেট", 450, "pcs", "Walton Plaza"),
        ("ceiling-fan-56", "Ceiling fan 56\"", "সিলিং ফ্যান ৫৬\"", 3800, "pcs", "Gazi Electronics"),
    ]),
    ("cleaning-supplies", "Cleaning supplies", "ক্লিনিং সামগ্রী", [
        ("floor-cleaner-1l", "Floor cleaner 1L", "ফ্লোর ক্লিনার ১ লিটার", 220, "bottle", "Mina Bazar"),
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
            for s_slug, s_en, s_bn, desc_en, desc_bn, price, emergency, minutes in items:
                Service.objects.update_or_create(
                    slug=s_slug,
                    defaults={
                        "category": cat, "name_en": s_en, "name_bn": s_bn, "description": desc_bn,
                        "base_price": price, "emergency_available": emergency, "duration_minutes": minutes,
                        "image_url": f"{IMG}/services/{s_slug}.jpg",
                    },
                )
        for order, (slug, en, bn, items) in enumerate(PRODUCT_CATEGORIES):
            cat, _ = Category.objects.update_or_create(
                slug=slug, defaults={"kind": "product", "name_en": en, "name_bn": bn, "sort_order": order}
            )
            for p_slug, p_en, p_bn, price, unit, shop in items:
                Product.objects.update_or_create(
                    slug=p_slug,
                    defaults={"category": cat, "name_en": p_en, "name_bn": p_bn, "price": price, "unit": unit, "stock": 50,
                              "shop_name": shop, "image_url": f"{IMG}/products/{p_slug}.jpg"},
                )
        self.stdout.write(self.style.SUCCESS("Catalog seeded."))
