"""Inbound SMS booking handler for low-data/offline customers.
Formats supported:
  1. Booking request: SS <SERVICE_CODE> <AREA> [ADDRESS]
     e.g.: SS CLEAN DHANMONDI Road 5
  2. Confirmation: YES <ORDER_ID>
  3. Status query: STATUS <ORDER_ID>
"""
import re
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from shohor_common import events, internal

from .models import Booking, Order, OrderItem
from . import logic

SERVICE_MAPPINGS = {
    "clean": {"slug": "home-cleaning", "name": "বাসা পরিষ্কার", "category": "cleaning", "price": "600.00"},
    "ac": {"slug": "ac-repair", "name": "এসি রিপেয়ার", "category": "ac-repair", "price": "800.00"},
    "plumb": {"slug": "plumbing", "name": "প্লাম্বিং সার্ভিস", "category": "plumbing", "price": "450.00"},
    "electric": {"slug": "electrical", "name": "ইলেকট্রিক্যাল সার্ভিস", "category": "electrical", "price": "500.00"},
    "appliance": {"slug": "appliance-repair", "name": "হোম অ্যাপ্লায়েন্স", "category": "appliance", "price": "550.00"},
}

AREA_MAPPINGS = {
    "dhanmondi": (1, "Dhanmondi"),
    "gulshan": (2, "Gulshan"),
    "banani": (3, "Banani"),
    "mirpur": (4, "Mirpur"),
    "uttara": (5, "Uttara"),
    "mohammadpur": (6, "Mohammadpur"),
}


def parse_and_process_sms(phone, text):
    text_clean = (text or "").strip()
    words = text_clean.split()
    if not words:
        return "ShohorSathi: এসএমএস বুকিং করতে লিখুন 'SS <SERVICE> <AREA> <ADDRESS>' (যেমন: SS CLEAN DHANMONDI Road 5)"

    cmd = words[0].upper()

    # 1. Confirmation: YES <ORDER_ID>
    if cmd in ("YES", "Y", "HA", "হ্যাঁ"):
        if len(words) < 2:
            return "ShohorSathi: কোন অর্ডারটি নিশ্চিত করতে চান? 'YES <ORDER_ID>' লিখে পাঠান।"
        order_id_match = re.search(r"\d+", words[1])
        if not order_id_match:
            return "ShohorSathi: ভুল অর্ডার নম্বর। আবার চেষ্টা করুন।"
        order_id = int(order_id_match.group())
        order = Order.objects.filter(pk=order_id, contact_phone=phone).first()
        if not order:
            return f"ShohorSathi: অর্ডার #{order_id} খুঁজে পাওয়া যায়নি।"
        if order.status != Order.Status.PENDING:
            return f"ShohorSathi: অর্ডার #{order_id} ইতিমধ্যে {order.status} অবস্থায় আছে।"

        with transaction.atomic():
            order.status = Order.Status.CONFIRMED
            order.save(update_fields=["status"])
            logic.log(order, Order.Status.CONFIRMED, "Confirmed via SMS")
            events.publish(
                "order.placed",
                {
                    "order_id": order.id,
                    "user_id": order.user_id,
                    "total": str(order.total),
                    "payment_method": order.payment_method,
                    "area_id": order.area_id,
                    "area_name": order.area_name,
                    "items": [],
                },
            )
            for booking in order.bookings.all():
                events.publish("booking.created", logic.booking_payload(booking))

        web_url = getattr(settings, "CUSTOMER_WEB_URL", "http://localhost:5173")
        return f"ShohorSathi: আপনার অর্ডার #{order.id} নিশ্চিত করা হয়েছে! প্রোভাইডার রওনা হলে ট্র্যাকিং লিংক পাবেন: {web_url}/orders/{order.id}"

    # 2. Status: STATUS <ORDER_ID>
    if cmd in ("STATUS", "INFO", "অবস্থা"):
        if len(words) < 2:
            return "ShohorSathi: 'STATUS <ORDER_ID>' লিখে পাঠান।"
        order_id_match = re.search(r"\d+", words[1])
        if not order_id_match:
            return "ShohorSathi: ভুল অর্ডার নম্বর।"
        order_id = int(order_id_match.group())
        order = Order.objects.filter(pk=order_id, contact_phone=phone).first()
        if not order:
            return f"ShohorSathi: অর্ডার #{order_id} খুঁজে পাওয়া যায়নি।"
        return f"ShohorSathi: অর্ডার #{order.id} স্ট্যাটাস: {order.status}। মোট: {order.total} টাকা।"

    # 3. Create Draft Booking: SS <SERVICE> <AREA> [ADDRESS]
    if cmd == "SS":
        if len(words) < 3:
            return "ShohorSathi: নিয়ম: 'SS <SERVICE> <AREA> <ADDRESS>' লিখুন (যেমন: SS CLEAN DHANMONDI Road 5)"
        srv_code = words[1].lower()
        area_code = words[2].lower()
        address_line = " ".join(words[3:]) if len(words) > 3 else "SMS Booking"

        srv = SERVICE_MAPPINGS.get(srv_code)
        if not srv:
            valid_srvs = ", ".join(SERVICE_MAPPINGS.keys())
            return f"ShohorSathi: সার্ভিস পাওয়া যায়নি। প্রযোজ্য সার্ভিস কোড: {valid_srvs}"

        area_info = AREA_MAPPINGS.get(area_code, (1, words[2].title()))
        area_id, area_name = area_info

        # Find or use phone number as user_id or lookup via auth
        try:
            user_info = internal.get("auth", f"/api/internal/users/by-phone/?phone={phone}") or {}
        except Exception:
            user_info = {}
        user_id = user_info.get("id") or 999999

        scheduled_date = timezone.localdate() + timedelta(days=1)
        price = Decimal(srv["price"])

        with transaction.atomic():
            order = Order.objects.create(
                user_id=user_id,
                subtotal=price,
                delivery_fee=Decimal("0"),
                total=price,
                payment_method=Order.PaymentMethod.COD,
                contact_name=user_info.get("full_name") or f"Customer {phone[-4:]}",
                contact_phone=phone,
                area_id=area_id,
                area_name=area_name,
                address_line=address_line,
                status=Order.Status.PENDING,
                note="Booked via SMS",
            )
            booking = Booking.objects.create(
                order=order,
                user_id=user_id,
                service_slug=srv["slug"],
                service_name=srv["name"],
                category_slug=srv["category"],
                price=price,
                warranty_days=7,
                scheduled_date=scheduled_date,
                slot="09-11",
                problem_description=f"SMS booking for {srv['name']} at {address_line}",
                arrival_code=f"{secrets.randbelow(10_000):04d}",
            )
            logic.log(order, Order.Status.PENDING, "SMS booking created (awaiting YES confirmation)", booking=booking)

        return (f"ShohorSathi: আপনার বুকিং ড্রাফট তৈরি হয়েছে (অর্ডার #{order.id}, {srv['name']}, {price} টাকা)। "
                f"নিশ্চিত করতে রিপ্লাই দিন 'YES {order.id}'")

    return "ShohorSathi: এসএমএস বুকিং নিয়ম: 'SS <SERVICE> <AREA> <ADDRESS>' লিখুন (যেমন: SS CLEAN DHANMONDI Road 5)।"

