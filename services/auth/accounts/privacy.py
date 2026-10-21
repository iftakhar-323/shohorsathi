"""Personal Data Protection Ordinance 2025 duties owned by the auth service: account deletion and data export.

Deletion anonymises the account here and announces `user.deleted`; every service that keeps personal data removes or
redacts its own copy (see each service's `user.deleted` task). Export gathers each service's copy of the user's data
through its internal `/api/internal/export/<user_id>/` endpoint.
"""
from django.db import transaction
from django.utils import timezone
from shohor_common import events, internal
from shohor_common.internal import ServiceUnavailable

from .models import User

# service -> what its export endpoint returns
EXPORTERS = ["order", "subscription", "provider", "custom_request", "loyalty", "city", "b2b"]


def export(user):
    data = {
        "generated_at": timezone.now().isoformat(),
        "profile": {"phone": user.phone, "full_name": user.full_name, "email": user.email, "role": user.role,
                    "date_joined": user.date_joined.isoformat(), "consent": {
                        "terms_version": user.terms_version,
                        "accepted_at": user.terms_accepted_at.isoformat() if user.terms_accepted_at else None,
                        "marketing_opt_in": user.marketing_opt_in}},
        "addresses": [{"label": a.label, "area": a.area.name_en, "line": a.line, "latitude": str(a.latitude or ""),
                       "longitude": str(a.longitude or "")} for a in user.addresses.select_related("area")],
    }
    for service in EXPORTERS:
        try:
            data[service] = internal.get(service, f"/api/internal/export/{user.id}/")
        except ServiceUnavailable:
            data[service] = {"error": "temporarily unavailable; please try again"}
    return data


@transaction.atomic
def delete_account(user):
    """Anonymise rather than drop the row, so orders and payments keep a valid user id for accounting."""
    uid = user.id
    user.phone = f"0{uid:010d}"[-11:]  # unique placeholder, never a real number pattern (starts 00…)
    user.full_name = "Deleted user"
    user.email = ""
    user.is_active = False
    user.marketing_opt_in = False
    user.deleted_at = timezone.now()
    user.set_unusable_password()
    user.save()
    user.addresses.all().delete()
    events.publish("user.deleted", {"user_id": uid})
    return user
