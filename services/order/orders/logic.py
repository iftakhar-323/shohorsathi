"""Order rules: pricing from the catalog, checkout, status changes and the events they emit."""
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from shohor_common import events, internal

from .models import Booking, Cart, CartItem, Order, OrderItem, TrackingEvent, WarrantyClaim

ACTIVE_BOOKING = {Booking.Status.PENDING, Booking.Status.CONFIRMED}


def catalog_item(item_type, slug):
    item = internal.get("catalog", f"/api/{item_type}s/{slug}/")
    if item is None or not item.get("is_active", True):
        return None
    price = item["price"] if item_type == "product" else item["base_price"]
    return {**item, "unit_price": Decimal(price), "name": item["name_bn"]}


def add_to_cart(user_id, item_type, slug, quantity):
    item = catalog_item(item_type, slug)
    if item is None:
        raise ValidationError({"slug": "This item is not available."})
    if item_type == "service":
        quantity = 1
    elif quantity > item["stock"]:
        raise ValidationError({"quantity": f"Only {item['stock']} left in stock."})
    cart, _ = Cart.objects.get_or_create(user_id=user_id)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        item_type=item_type,
        slug=slug,
        defaults={"name": item["name"], "unit_price": item["unit_price"], "quantity": quantity},
    )
    if not created and item_type == "product":
        cart_item.quantity += quantity
        cart_item.unit_price = item["unit_price"]
        cart_item.save(update_fields=["quantity", "unit_price"])
    return cart_item


def log(order, status, note="", booking=None):
    TrackingEvent.objects.create(order=order, booking=booking, status=status, note=note)


def booking_payload(booking, source="booking", source_id=None, price=None):
    order = booking.order
    return {
        "source": source,
        "source_id": source_id or booking.id,
        "booking_id": booking.id,
        "order_id": order.id,
        "user_id": booking.user_id,
        "title": booking.service_name,
        "service_slug": booking.service_slug,
        "category_slug": booking.category_slug,
        "area_id": order.area_id,
        "area_name": order.area_name,
        "address_line": order.address_line,
        "latitude": str(order.latitude) if order.latitude is not None else None,
        "longitude": str(order.longitude) if order.longitude is not None else None,
        "customer_name": order.contact_name,
        "customer_phone": order.contact_phone,
        "scheduled_date": booking.scheduled_date.isoformat(),
        "slot": booking.slot,
        "amount": str(booking.price if price is None else price),
        "is_emergency": booking.is_emergency,
        "required_gender": booking.required_gender,
        "description": booking.problem_description,
        "photo_urls": booking.photo_urls,
    }


@transaction.atomic
def checkout(user_id, data):
    cart = Cart.objects.filter(user_id=user_id).first()
    items = list(cart.items.all()) if cart else []
    if not items:
        raise ValidationError({"cart": "Your cart is empty."})

    details = {int(k): v for k, v in data.get("service_details", {}).items()}
    priced, unavailable = [], []
    for cart_item in items:
        item = catalog_item(cart_item.item_type, cart_item.slug)
        if item is None:
            unavailable.append(cart_item.name)
        elif cart_item.item_type == "service" and cart_item.id not in details:
            raise ValidationError({"service_details": f"Pick a date and time for {cart_item.name}."})
        else:
            priced.append((cart_item, item))
    if unavailable:
        raise ValidationError({"cart": f"No longer available: {', '.join(unavailable)}"})

    products = [(c, i) for c, i in priced if c.item_type == "product"]
    services = [(c, i) for c, i in priced if c.item_type == "service"]
    for cart_item, item in services:
        # Neighbours who filled a group deal for this service book it at the deal price.
        deal = internal.get("catalog", "/api/internal/group-deals/discount/", user_id=user_id, slug=cart_item.slug) or {}
        if deal.get("percent"):
            item["unit_price"] = (item["unit_price"] * (100 - Decimal(deal["percent"])) / 100).quantize(Decimal("1"))
    surcharges = {}
    for cart_item, item in services:
        d = details[cart_item.id]
        if d.get("is_emergency"):
            if not item.get("emergency_available"):
                raise ValidationError({"service_details": f"{cart_item.name} is not offered as an emergency service."})
            if d["scheduled_date"] != timezone.localdate():
                raise ValidationError({"service_details": "Emergency bookings are for today."})
            surcharges[cart_item.id] = (item["unit_price"] * Decimal(settings.EMERGENCY_SURCHARGE_PERCENT) / 100).quantize(Decimal("1"))
    subtotal = sum((i["unit_price"] * c.quantity for c, i in priced), Decimal("0")) + sum(surcharges.values(), Decimal("0"))
    delivery_fee = Decimal(settings.ORDER_DELIVERY_FEE) if products else Decimal("0")

    ll_phone = data.get("landlord_phone", "")
    order = Order.objects.create(
        user_id=user_id,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=subtotal + delivery_fee,
        payment_method=data.get("payment_method", Order.PaymentMethod.COD),
        **{k: data[k] for k in ("contact_name", "contact_phone", "address_line", "area_id", "area_name")},
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        note=data.get("note", ""),
        landlord_phone=ll_phone,
        landlord_approval_status="pending" if ll_phone else "none",
        landlord_token=secrets.token_hex(16) if ll_phone else "",
    )
    for cart_item, item in products:
        OrderItem.objects.create(
            order=order, slug=cart_item.slug, name=item["name"], unit_price=item["unit_price"], quantity=cart_item.quantity
        )
    bookings = []
    for cart_item, item in services:
        d = details[cart_item.id]
        bookings.append(
            Booking.objects.create(
                order=order,
                user_id=user_id,
                service_slug=cart_item.slug,
                service_name=item["name"],
                category_slug=item.get("category_slug", ""),
                price=item["unit_price"] + surcharges.get(cart_item.id, Decimal("0")),
                surcharge=surcharges.get(cart_item.id, Decimal("0")),
                warranty_days=item.get("warranty_days", 7),
                scheduled_date=d["scheduled_date"],
                slot=d["slot"],
                problem_description=d.get("problem_description", ""),
                photo_urls=d.get("photo_urls", []),
                is_emergency=d.get("is_emergency", False),
                required_gender="female" if d.get("prefer_female") else "",
                arrival_code=f"{secrets.randbelow(10_000):04d}",
            )
        )
    cart.items.all().delete()
    log(order, Order.Status.PENDING, "Order placed")
    settle_loyalty(order, data)

    events.publish(
        "order.placed",
        {
            "order_id": order.id,
            "user_id": user_id,
            "total": str(order.total),
            "payment_method": order.payment_method,
            "area_id": order.area_id,
            "area_name": order.area_name,
            "items": [{"slug": c.slug, "quantity": c.quantity} for c, _ in products],
        },
    )
    if order.landlord_token:
        events.publish("order.landlord_approval_requested", {
            "order_id": order.id, "user_id": user_id, "landlord_phone": order.landlord_phone, "tenant_name": order.contact_name,
            "address": order.address_line, "area_name": order.area_name, "total": str(order.total), "token": order.landlord_token,
        })
    # Online orders reach providers only after the payment goes through (see payment_succeeded).
    if order.payment_method != Order.PaymentMethod.ONLINE:
        for booking in bookings:
            events.publish("booking.created", booking_payload(booking))
    return order


def settle_loyalty(order, data):
    """Points as a discount and/or wallet as payment, settled with the loyalty service during checkout."""
    if data.get("organization_id"):
        status, member = internal.post("b2b", "/api/internal/b2b/membership/", {"organization_id": data["organization_id"], "user_id": order.user_id})
        if status != 200 or not member.get("ok"):
            raise ValidationError({"organization_id": "You are not a member of this organization."})
        order.organization_id = data["organization_id"]
    points = data.get("redeem_points") or 0
    try:
        if points:
            status, body = internal.post("loyalty", "/api/internal/loyalty/redeem-points/",
                                         {"user_id": order.user_id, "order_id": order.id, "points": points, "subtotal": str(order.subtotal)})
            discount = Decimal(body.get("discount", "0")) if status == 200 else Decimal("0")
            order.discount = min(discount, order.subtotal)
            order.points_redeemed = int(discount / Decimal(settings.POINT_VALUE_TAKA)) if discount else 0
            order.total = order.subtotal + order.delivery_fee - order.discount
        if order.payment_method == Order.PaymentMethod.WALLET:
            status, body = internal.post("loyalty", "/api/internal/loyalty/wallet-pay/", {"user_id": order.user_id, "order_id": order.id, "amount": str(order.total)})
            if status != 200:
                raise ValidationError({"payment_method": "Not enough wallet balance."})
            order.payment_status = Order.PaymentStatus.PAID
    except ValidationError:
        internal.post("loyalty", "/api/internal/loyalty/reverse/", {"order_id": order.id})
        raise
    order.save()


@transaction.atomic
def payment_succeeded(payload):
    if payload.get("purpose") != "order":
        return
    order = Order.objects.select_for_update().filter(pk=payload["reference_id"]).first()
    if order is None or order.payment_status == Order.PaymentStatus.PAID:
        return
    order.payment_status = Order.PaymentStatus.PAID
    order.save(update_fields=["payment_status", "updated_at"])
    log(order, "paid", f"Paid online ৳{payload['amount']}")
    if order.status != Order.Status.CANCELLED and order.payment_method == Order.PaymentMethod.ONLINE:
        for booking in order.bookings.filter(status=Booking.Status.PENDING):
            events.publish("booking.created", booking_payload(booking))


def payment_refunded(payload):
    if payload.get("purpose") == "order" and payload.get("full"):
        Order.objects.filter(pk=payload["reference_id"]).update(payment_status=Order.PaymentStatus.REFUNDED)


def status_payload(order):
    return {"order_id": order.id, "user_id": order.user_id, "status": order.status, "total": str(order.total),
            "payment_method": order.payment_method, "organization_id": order.organization_id}


def refresh_order_status(order):
    """Derive the order's overall status from its bookings and product delivery."""
    if order.status == Order.Status.CANCELLED:
        return
    bookings = list(order.bookings.all())
    live = [b for b in bookings if b.status != Booking.Status.CANCELLED]
    has_products = order.items.exists()
    products_done = not has_products or order.status == Order.Status.DELIVERED

    if not has_products and not live:
        new = Order.Status.CANCELLED
    elif products_done and all(b.status == Booking.Status.COMPLETED for b in live):
        new = Order.Status.COMPLETED
    elif order.status == Order.Status.PENDING and any(b.status != Booking.Status.PENDING for b in live):
        new = Order.Status.CONFIRMED
    else:
        return
    order.status = new
    fields = ["status", "updated_at"]
    if new == Order.Status.COMPLETED and order.payment_method == Order.PaymentMethod.COD:
        order.payment_status = Order.PaymentStatus.PAID
        fields.append("payment_status")
    order.save(update_fields=fields)
    log(order, new)
    events.publish("order.status_changed", status_payload(order))


@transaction.atomic
def cancel_booking(booking, reason="Cancelled by customer"):
    if booking.status not in ACTIVE_BOOKING:
        raise ValidationError({"status": "This booking can no longer be cancelled."})
    booking.status = Booking.Status.CANCELLED
    booking.save(update_fields=["status"])
    log(booking.order, booking.status, reason, booking)
    events.publish("booking.cancelled", {"source": "booking", "source_id": booking.id, "user_id": booking.user_id})
    refresh_order_status(booking.order)


@transaction.atomic
def cancel_order(order):
    if order.status != Order.Status.PENDING or any(b.status not in ACTIVE_BOOKING for b in order.bookings.all()):
        raise ValidationError({"status": "This order can no longer be cancelled."})
    for booking in order.bookings.exclude(status=Booking.Status.CANCELLED):
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status"])
        events.publish("booking.cancelled", {"source": "booking", "source_id": booking.id, "user_id": booking.user_id})
    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    log(order, order.status, "Cancelled by customer")
    events.publish("order.status_changed", status_payload(order))


@transaction.atomic
def reschedule(booking, scheduled_date, slot):
    if booking.status not in ACTIVE_BOOKING:
        raise ValidationError({"status": "This booking can no longer be rescheduled."})
    if scheduled_date < timezone.localdate():
        raise ValidationError({"scheduled_date": "Pick today or a later date."})
    booking.scheduled_date, booking.slot = scheduled_date, slot
    booking.save(update_fields=["scheduled_date", "slot"])
    log(booking.order, "rescheduled", f"{scheduled_date} {slot}", booking)
    events.publish(
        "booking.rescheduled",
        {"source": "booking", "source_id": booking.id, "scheduled_date": scheduled_date.isoformat(), "slot": slot},
    )


JOB_TO_BOOKING = {
    "open": Booking.Status.PENDING,
    "assigned": Booking.Status.PENDING,
    "accepted": Booking.Status.CONFIRMED,
    "on_the_way": Booking.Status.ON_THE_WAY,
    "working": Booking.Status.WORKING,
    "completed": Booking.Status.COMPLETED,
    "cancelled": Booking.Status.CANCELLED,
}


@transaction.atomic
def apply_job_status(payload):
    if payload.get("source") == "warranty":
        if payload["status"] == "completed":
            WarrantyClaim.objects.filter(pk=payload["source_id"]).update(status=WarrantyClaim.Status.RESOLVED)
        return
    if payload.get("source") != "booking":
        return
    booking = Booking.objects.select_for_update().filter(pk=payload["source_id"]).first()
    new = JOB_TO_BOOKING.get(payload["status"])
    if booking is None or new is None or booking.status in (Booking.Status.COMPLETED, Booking.Status.CANCELLED):
        return
    booking.status = new
    if new == Booking.Status.PENDING:
        booking.provider_id, booking.provider_name, booking.provider_phone = None, "", ""
    elif payload.get("provider_id"):
        booking.provider_id = payload["provider_id"]
        booking.provider_name = payload.get("provider_name", "")
        booking.provider_phone = payload.get("provider_phone", "")
    if new == Booking.Status.COMPLETED:
        booking.completed_at = timezone.now()
    booking.save()
    log(booking.order, payload["status"], payload.get("note", ""), booking)
    refresh_order_status(booking.order)


def overdue_deliveries():
    """Product orders not delivered within the promised days (guidelines: 5 days in the same city)."""
    cutoff = timezone.now() - timedelta(days=int(settings.ORDER_DELIVERY_DEADLINE_DAYS))
    return Order.objects.filter(items__isnull=False, created_at__lt=cutoff,
                                status__in=[Order.Status.PENDING, Order.Status.CONFIRMED, Order.Status.ON_THE_WAY]).distinct()


def set_product_status(order, status):
    allowed = {
        Order.Status.PENDING: {Order.Status.CONFIRMED, Order.Status.CANCELLED},
        Order.Status.CONFIRMED: {Order.Status.ON_THE_WAY, Order.Status.CANCELLED},
        Order.Status.ON_THE_WAY: {Order.Status.DELIVERED},
    }
    if status not in allowed.get(order.status, set()):
        raise ValidationError({"status": f"Cannot move from {order.status} to {status}."})
    with transaction.atomic():
        order.status = status
        order.save(update_fields=["status", "updated_at"])
        log(order, status, "Updated by admin")
        if status == Order.Status.CANCELLED:
            for booking in order.bookings.filter(status__in=ACTIVE_BOOKING):
                booking.status = Booking.Status.CANCELLED
                booking.save(update_fields=["status"])
                events.publish("booking.cancelled", {"source": "booking", "source_id": booking.id, "user_id": booking.user_id})
        events.publish("order.status_changed", status_payload(order))
        refresh_order_status(order)


def open_warranty_claim(booking, description, photo_urls):
    if booking.status != Booking.Status.COMPLETED or booking.completed_at is None:
        raise ValidationError({"booking": "Warranty applies to completed jobs only."})
    if timezone.now() > booking.completed_at + timedelta(days=booking.warranty_days):
        raise ValidationError({"booking": f"The {booking.warranty_days}-day warranty has ended."})
    if booking.warranty_claims.filter(status__in=[WarrantyClaim.Status.OPEN, WarrantyClaim.Status.APPROVED]).exists():
        raise ValidationError({"booking": "A warranty claim is already in progress."})
    return WarrantyClaim.objects.create(
        booking=booking, user_id=booking.user_id, description=description, photo_urls=photo_urls
    )


@transaction.atomic
def approve_warranty_claim(claim, note=""):
    if claim.status != WarrantyClaim.Status.OPEN:
        raise ValidationError({"status": "Claim already handled."})
    claim.status, claim.admin_note = WarrantyClaim.Status.APPROVED, note
    claim.save(update_fields=["status", "admin_note"])
    booking = claim.booking
    payload = booking_payload(booking, source="warranty", source_id=claim.id, price=Decimal("0"))
    payload["title"] = f"Warranty re-work: {booking.service_name}"
    payload["description"] = claim.description
    payload["preferred_provider_id"] = booking.provider_id
    events.publish("booking.created", payload)


def landlord_decide(order, approve):
    """The landlord, through the texted link, agrees (or not) that the repair is deducted from next month's rent."""
    if order.landlord_approval_status != "pending":
        raise ValidationError({"order": f"Already {order.landlord_approval_status}."})
    order.landlord_approval_status = "approved" if approve else "rejected"
    order.landlord_approved_at = timezone.now()
    if approve:
        order.rent_deduction_receipt_number = f"RDR-{order.number}"
    order.save(update_fields=["landlord_approval_status", "landlord_approved_at", "rent_deduction_receipt_number"])
    events.publish("order.landlord_decided", {"order_id": order.id, "user_id": order.user_id, "approved": approve})
    return order
