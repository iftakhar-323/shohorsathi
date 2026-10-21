from django.db import transaction
from shohor_common.privacy import DELETED_NAME, iso

from . import logic
from .models import StudentVerification, Subscription


def collect(user_id):
    return [
        {"plan": s.plan.name_en, "status": s.status, "from": iso(s.start_date), "to": iso(s.end_date), "price": str(s.price),
         "address": f"{s.address_line}, {s.area_name}", "members": s.members,
         "visits": [{"date": iso(v.date), "kind": v.kind, "status": v.status, "rating": v.rating, "feedback": v.feedback} for v in s.visits.all()]}
        for s in Subscription.objects.filter(user_id=user_id).select_related("plan").prefetch_related("visits")
    ]


@transaction.atomic
def forget(user_id):
    for sub in Subscription.objects.filter(user_id=user_id).exclude(status__in=["cancelled", "expired"]):
        logic.cancel(sub)
    Subscription.objects.filter(user_id=user_id).update(customer_name=DELETED_NAME, customer_phone="", address_line="", latitude=None, longitude=None, members=[])
    StudentVerification.objects.filter(user_id=user_id).delete()
