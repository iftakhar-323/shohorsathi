from django.db import transaction
from shohor_common.privacy import DELETED_NAME, iso

from .models import Booking, CartItem, Order


def collect(user_id):
    return [
        {"number": o.number, "status": o.status, "total": str(o.total), "payment": o.payment_method, "created_at": iso(o.created_at),
         "address": f"{o.address_line}, {o.area_name}",
         "items": [{"name": i.name, "quantity": i.quantity, "price": str(i.unit_price)} for i in o.items.all()],
         "bookings": [{"service": b.service_name, "date": iso(b.scheduled_date), "status": b.status, "provider": b.provider_name,
                       "problem": b.problem_description} for b in o.bookings.all()]}
        for o in Order.objects.filter(user_id=user_id).prefetch_related("items", "bookings")
    ]


@transaction.atomic
def forget(user_id):
    """Orders stay for accounting; the person's contact details and problem notes go."""
    Order.objects.filter(user_id=user_id).update(contact_name=DELETED_NAME, contact_phone="", address_line="", latitude=None, longitude=None, note="")
    Booking.objects.filter(user_id=user_id).update(problem_description="", photo_urls=[])
    CartItem.objects.filter(cart__user_id=user_id).delete()
