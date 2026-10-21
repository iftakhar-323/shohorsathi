from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError
from shohor_common import events

from .models import CounterOffer, CustomRequest, Quote, StatusLog

S = CustomRequest.Status


def move(req, status, note="", allowed_from=None):
    if allowed_from is not None and req.status not in allowed_from:
        raise ValidationError({"status": f"Not possible while the request is {req.status}."})
    req.status = status
    req.save()
    StatusLog.objects.create(request=req, status=status, note=note)
    events.publish(
        "custom_request.status_changed",
        {"request_id": req.id, "user_id": req.user_id, "status": status, "service_type": req.service_type},
    )
    return req


@transaction.atomic
def create(user_id, name, phone, data):
    req = CustomRequest.objects.create(user_id=user_id, customer_name=name, customer_phone=phone, **data)
    StatusLog.objects.create(request=req, status=S.SUBMITTED)
    return req


@transaction.atomic
def send_quote(req, data):
    if req.status not in (S.UNDER_REVIEW, S.COUNTERED, S.SUBMITTED):
        raise ValidationError({"status": f"Cannot quote while the request is {req.status}."})
    category = data.pop("category_slug", "")
    if category:
        req.category_slug = category
    if not req.category_slug:
        raise ValidationError({"category_slug": "Pick the provider category that will do this job."})
    req.quotes.update(is_current=False)
    quote = Quote.objects.create(request=req, **data)
    move(req, S.QUOTE_SENT, f"Quote ৳{quote.total}")
    events.publish("custom_request.quoted", {"request_id": req.id, "user_id": req.user_id, "total": str(quote.total)})
    return quote


@transaction.atomic
def accept(req):
    quote = req.current_quote
    if req.status != S.QUOTE_SENT or quote is None:
        raise ValidationError({"status": "There is no quote to accept."})
    req.final_amount = quote.total
    percent = Decimal(settings.CUSTOM_REQUEST_ADVANCE_PERCENT)
    req.advance_amount = (quote.total * percent / 100).quantize(Decimal("1"), ROUND_HALF_UP)
    move(req, S.ACCEPTED, "Quote accepted")
    events.publish(
        "custom_request.accepted",
        {
            "request_id": req.id,
            "user_id": req.user_id,
            "title": req.service_type,
            "category_slug": req.category_slug,
            "area_id": req.area_id,
            "area_name": req.area_name,
            "address_line": req.address_line,
            "latitude": str(req.latitude) if req.latitude is not None else None,
            "longitude": str(req.longitude) if req.longitude is not None else None,
            "customer_name": req.customer_name,
            "customer_phone": req.customer_phone,
            "scheduled_date": req.preferred_date.isoformat(),
            "slot": "09-11",
            "amount": str(quote.total),
            # The quote's platform fee is the platform's cut, instead of the standard commission.
            "commission_override": str(quote.platform_fee),
            "description": req.description,
            "photo_urls": req.media_urls,
            "advance_amount": str(req.advance_amount),
        },
    )
    return req


@transaction.atomic
def counter(req, amount, message):
    if req.status != S.QUOTE_SENT:
        raise ValidationError({"status": "You can counter only a sent quote."})
    if CounterOffer.objects.filter(request=req).exists():
        raise ValidationError({"counter": "Only one counter-offer is allowed. Accept or reject the new quote."})
    CounterOffer.objects.create(request=req, amount=amount, message=message)
    return move(req, S.COUNTERED, f"Counter-offer ৳{amount}")


JOB_TO_REQUEST = {
    "open": S.ACCEPTED,
    "assigned": S.PROVIDER_ASSIGNED,
    "accepted": S.PROVIDER_ASSIGNED,
    "on_the_way": S.IN_PROGRESS,
    "working": S.IN_PROGRESS,
    "completed": S.COMPLETED,
    "cancelled": S.CANCELLED,
}


@transaction.atomic
def apply_job_status(payload):
    if payload.get("source") != "custom_request":
        return
    req = CustomRequest.objects.select_for_update().filter(pk=payload["source_id"]).first()
    new = JOB_TO_REQUEST.get(payload["status"])
    if req is None or new is None or req.status in (S.COMPLETED, S.CANCELLED) or req.status == new:
        return
    req.provider_id = payload.get("provider_id")
    req.provider_name = payload.get("provider_name", "")
    req.provider_phone = payload.get("provider_phone", "")
    move(req, new, payload.get("note", ""))


def mark_advance_paid(payload):
    if payload.get("purpose") == "custom_request_advance":
        CustomRequest.objects.filter(pk=payload["reference_id"]).update(advance_paid=True)
