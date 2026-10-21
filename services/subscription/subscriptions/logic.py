"""Subscription pricing, schedules, skip/pause/cancel, renewals and dispatching visits as provider jobs."""
from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from shohor_common import events, internal

from .models import Addon, Plan, PlanPrice, StudentVerification, Subscription, Visit

S = Subscription.Status
V = Visit.Status
CENT = Decimal("0.01")
MEAL_SLOTS = {"breakfast": "09-11", "lunch": "11-13", "dinner": "18-20"}


def money(x):
    return Decimal(x).quantize(CENT, ROUND_HALF_UP)


# ---- pricing ----------------------------------------------------------------------------------

def base_price(plan, duration, home_size):
    size = home_size if plan.sizes_apply else 0
    row = PlanPrice.objects.filter(plan=plan, duration_days=duration, home_size=size).first()
    if row is None:
        raise ValidationError({"duration_days": "This plan is not offered for that duration/home size."})
    return row.price


def quote(plan, duration, home_size=0, prepaid_months=1, addon_slugs=(), user_id=None, members=0):
    price = base_price(plan, duration, home_size)
    lines = [{"label": "plan", "amount": str(price)}]
    addons = list(Addon.objects.filter(slug__in=addon_slugs, is_active=True))
    for a in addons:
        if plan.category not in a.categories:
            raise ValidationError({"addons": f"{a.name_en} is not available for this plan."})
        price += a.price
        lines.append({"label": f"addon:{a.slug}", "amount": str(a.price)})
    months = prepaid_months if duration == 30 else 1
    discount_pct = Decimal(settings.PREPAY_DISCOUNTS.get(str(months), 0)) if months > 1 else Decimal("0")
    total = price * months
    discount = money(total * discount_pct / 100)
    if discount:
        lines.append({"label": f"prepay_{months}_months", "amount": f"-{discount}"})
    student = bool(user_id) and plan.category in ("meal", "tiffin") and StudentVerification.objects.filter(
        user_id=user_id, status=StudentVerification.Status.APPROVED
    ).exists()
    student_off = money((total - discount) * Decimal(settings.STUDENT_DISCOUNT_PERCENT) / 100) if student else Decimal("0")
    if student_off:
        lines.append({"label": "student", "amount": f"-{student_off}"})
    final = money(total - discount - student_off)
    per_member = money(final / members) if members > 1 else None
    return {
        "total": final,
        "lines": lines,
        "months": months,
        "student_discount": bool(student_off),
        "per_member": str(per_member) if per_member else None,
        "addons": [a.slug for a in addons],
    }


# ---- schedules --------------------------------------------------------------------------------

def service_days(plan, start, days, weekday):
    """Dates a non-meal plan visits within [start, start+days)."""
    end = start + timedelta(days=days)
    f = plan.frequency
    if f in (Plan.Frequency.DAILY, Plan.Frequency.ALTERNATE, Plan.Frequency.EVERY_3_DAYS):
        step = {"daily": 1, "alternate": 2, "every_3_days": 3}[f]
        return [start + timedelta(days=i) for i in range(0, days, step)]
    first = start + timedelta(days=(weekday - start.weekday()) % 7)
    weekly = []
    d = first
    while d < end:
        weekly.append(d)
        d += timedelta(days=7)
    if f == Plan.Frequency.WEEKLY:
        return weekly
    if f == Plan.Frequency.BIWEEKLY:
        return weekly[::2] or [first if first < end else start]
    return weekly[:: 4] or [first if first < end else start]  # monthly


def build_visits(sub):
    plan = sub.plan
    rows = []
    if plan.category in (Plan.Category.MEAL, Plan.Category.TIFFIN):
        for i in range(sub.duration_days):
            day = sub.start_date + timedelta(days=i)
            for meal in plan.meal_types:
                rows.append(Visit(subscription=sub, date=day, slot=MEAL_SLOTS.get(meal, sub.slot), kind=Visit.Kind.MEAL, meal_type=meal, value=0))
    else:
        dates = service_days(plan, sub.start_date, sub.duration_days, sub.preferred_weekday)
        rows = [Visit(subscription=sub, date=d, slot=sub.slot, value=0) for d in dates]
        deep = round(plan.deep_cleans_per_30_days * sub.duration_days / 30)
        for d in dates[-deep:] if deep else []:
            rows.append(Visit(subscription=sub, date=d, slot=sub.slot, kind=Visit.Kind.DEEP_CLEAN, value=0))
    months = sub.prepaid_months if sub.duration_days == 30 else 1
    if months > 1:  # prepaid months: repeat the schedule for each month
        extra = []
        for m in range(1, months):
            shift = timedelta(days=30 * m)
            extra += [Visit(subscription=sub, date=v.date + shift, slot=v.slot, kind=v.kind, meal_type=v.meal_type, value=0) for v in rows]
        rows += extra
    if rows:
        each = money(sub.price / len(rows))
        for v in rows:
            v.value = each
    Visit.objects.bulk_create(rows)
    return rows


def cutoff_for(visit_date):
    """Changes to a day's visits close at the cutoff hour (default 22:00) the evening before."""
    day_before = visit_date - timedelta(days=1)
    return timezone.make_aware(datetime.combine(day_before, time(settings.SUBSCRIPTION_CUTOFF_HOUR)))


def can_change(visit, now=None):
    return visit.status == V.SCHEDULED and (now or timezone.now()) < cutoff_for(visit.date)


# ---- lifecycle --------------------------------------------------------------------------------

def publish_status(sub, cancelled_visit_ids=()):
    events.publish(
        "subscription.status_changed",
        {"subscription_id": sub.id, "user_id": sub.user_id, "status": sub.status, "cancelled_visit_ids": list(cancelled_visit_ids)},
    )


def create(user_id, name, phone, data, renewed_from=None):
    plan = data["plan"]
    if not plan.is_active:
        raise ValidationError({"plan": "This plan is not available."})
    start = data["start_date"]
    if start <= timezone.localdate():
        raise ValidationError({"start_date": "Start from tomorrow or later."})
    q = quote(plan, data["duration_days"], data.get("home_size", 0), data.get("prepaid_months", 1),
              data.get("addons", []), user_id, len(data.get("members", [])))
    months = q["months"]
    credit = renewed_from.credit if renewed_from else Decimal("0")
    online = data.get("payment_method") == "online"
    with transaction.atomic():
        sub = Subscription.objects.create(
            user_id=user_id,
            customer_name=name,
            customer_phone=phone,
            plan=plan,
            duration_days=data["duration_days"],
            home_size=data.get("home_size", 0),
            preferred_weekday=data.get("preferred_weekday", 5),
            slot=data.get("slot", "09-11"),
            start_date=start,
            end_date=start + timedelta(days=data["duration_days"] * months - 1),
            area_id=data["area_id"],
            area_name=data["area_name"],
            address_line=data["address_line"],
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            diet=data.get("diet", ""),
            required_gender="female" if data.get("prefer_female") else "",
            addons=q["addons"],
            members=data.get("members", []),
            prepaid_months=months,
            student_discount=q["student_discount"],
            price=q["total"],
            credit_applied=min(credit, q["total"]),
            payment_method=data.get("payment_method", "cod"),
            agreement_id=data.get("agreement_id", ""),
            status=S.PENDING_PAYMENT if online else S.ACTIVE,
            auto_renew=data.get("auto_renew", True),
            renewed_from=renewed_from,
            preferred_provider_id=renewed_from.preferred_provider_id if renewed_from else None,
            preferred_provider_name=renewed_from.preferred_provider_name if renewed_from else "",
        )
        build_visits(sub)

    if sub.payment_method == "bkash_auto" and sub.agreement_id and sub.amount_due > 0:
        status_code, res = internal.post(
            "payment",
            "/api/internal/charge-agreement/",
            {"agreement_id": sub.agreement_id, "purpose": "subscription", "reference_id": sub.id, "amount": str(sub.amount_due)},
        )
        if status_code in (200, 201) and res and res.get("status") in ("held", "released"):
            sub.paid = True
            sub.status = S.ACTIVE
            sub.save(update_fields=["paid", "status"])
        else:
            sub.status = S.PENDING_PAYMENT
            sub.save(update_fields=["status"])
    events.publish(
        "subscription.created",
        {"subscription_id": sub.id, "user_id": user_id, "plan": plan.slug, "category": plan.category,
         "amount": str(sub.amount_due), "renewal": bool(renewed_from)},
    )
    return sub


@transaction.atomic
def skip(visit):
    if not can_change(visit):
        raise ValidationError({"visit": "Too late to skip: changes close at 10 PM the day before."})
    visit.status = V.SKIPPED
    visit.save(update_fields=["status"])
    Subscription.objects.filter(pk=visit.subscription_id).update(credit=visit.subscription.credit + visit.value)
    return visit


@transaction.atomic
def unskip(visit):
    if visit.status != V.SKIPPED or timezone.now() >= cutoff_for(visit.date):
        raise ValidationError({"visit": "This visit can't be restored."})
    sub = visit.subscription
    visit.status = V.SCHEDULED
    visit.save(update_fields=["status"])
    sub.credit = max(sub.credit - visit.value, Decimal("0"))
    sub.save(update_fields=["credit"])
    return visit


@transaction.atomic
def pause(sub, until):
    if sub.status != S.ACTIVE:
        raise ValidationError({"status": "Only an active subscription can be paused."})
    if until <= timezone.localdate():
        raise ValidationError({"until": "Pick a future date."})
    now = timezone.now()
    paused = [v for v in sub.visits.filter(status=V.SCHEDULED, date__lt=until) if now < cutoff_for(v.date)]
    for v in paused:
        v.status = V.SKIPPED
        v.save(update_fields=["status"])
    sub.credit += sum((v.value for v in paused), Decimal("0"))
    sub.status, sub.paused_until = S.PAUSED, until
    sub.save(update_fields=["credit", "status", "paused_until"])
    publish_status(sub)
    return sub


@transaction.atomic
def resume(sub):
    if sub.status != S.PAUSED:
        raise ValidationError({"status": "Subscription is not paused."})
    sub.status, sub.paused_until = S.ACTIVE, None
    sub.save(update_fields=["status", "paused_until"])
    publish_status(sub)
    return sub


@transaction.atomic
def cancel(sub):
    if sub.status in (S.CANCELLED, S.EXPIRED):
        raise ValidationError({"status": "Already ended."})
    future = list(sub.visits.filter(status__in=[V.SCHEDULED, V.DISPATCHED], date__gt=timezone.localdate()))
    dispatched = [v.id for v in future if v.status == V.DISPATCHED]
    sub.visits.filter(id__in=[v.id for v in future]).update(status=V.CANCELLED)
    if sub.paid:
        sub.credit += sum((v.value for v in future), Decimal("0"))
    sub.status, sub.auto_renew = S.CANCELLED, False
    sub.save(update_fields=["status", "auto_renew", "credit"])
    publish_status(sub, dispatched)
    return sub


@transaction.atomic
def change_address(sub, data):
    for f in ("area_id", "area_name", "address_line", "latitude", "longitude"):
        if f in data:
            setattr(sub, f, data[f])
    sub.save()
    return sub


@transaction.atomic
def rate(visit, rating, feedback=""):
    if visit.status != V.COMPLETED:
        raise ValidationError({"visit": "You can rate a completed visit only."})
    if visit.rating:
        raise ValidationError({"visit": "Already rated."})
    visit.rating, visit.feedback = rating, feedback
    visit.save(update_fields=["rating", "feedback"])
    if visit.provider_id:
        events.publish("review.created", {"source": "subscription_visit", "source_id": visit.id, "user_id": visit.subscription.user_id,
                                          "provider_user_id": visit.provider_id, "rating": rating, "comment": feedback})
    sub = visit.subscription
    # A bad meal is refunded as credit; a bad clean can be redone (see reclean).
    if visit.kind == Visit.Kind.MEAL and rating <= 2:
        sub.credit += visit.value
        sub.save(update_fields=["credit"])
    return visit


@transaction.atomic
def reclean(visit):
    if visit.kind not in (Visit.Kind.VISIT, Visit.Kind.DEEP_CLEAN) or visit.status != V.COMPLETED:
        raise ValidationError({"visit": "Re-clean applies to completed cleaning visits."})
    if visit.completed_at and timezone.now() > visit.completed_at + timedelta(hours=settings.RECLEAN_WINDOW_HOURS):
        raise ValidationError({"visit": "The free re-clean window (48 hours) has passed."})
    if hasattr(visit, "reclean"):
        raise ValidationError({"visit": "A re-clean was already requested."})
    redo = Visit.objects.create(
        subscription=visit.subscription, date=timezone.localdate() + timedelta(days=1), slot=visit.slot,
        kind=Visit.Kind.RECLEAN, value=Decimal("0"), reclean_of=visit,
    )
    dispatch(redo)  # tomorrow: the nightly run has passed or is about to, so dispatch now
    return redo


# ---- dispatch & job events --------------------------------------------------------------------

def dispatch(visit):
    sub = visit.subscription
    plan = sub.plan
    title = f"{plan.name_bn} — {'মিল ' + visit.meal_type if visit.kind == Visit.Kind.MEAL else visit.get_kind_display()}"
    events.publish(
        "subscription.visit_due",
        {
            "visit_id": visit.id,
            "user_id": sub.user_id,
            "title": title,
            "category_slug": plan.provider_category,
            "area_id": sub.area_id,
            "area_name": sub.area_name,
            "address_line": sub.address_line,
            "latitude": str(sub.latitude) if sub.latitude is not None else None,
            "longitude": str(sub.longitude) if sub.longitude is not None else None,
            "customer_name": sub.customer_name,
            "customer_phone": sub.customer_phone,
            "scheduled_date": visit.date.isoformat(),
            "slot": visit.slot,
            "amount": str(visit.value),
            "description": f"{plan.name_en}; diet: {sub.diet}" if sub.diet else plan.name_en,
            "preferred_provider_id": sub.preferred_provider_id,
            "required_gender": sub.required_gender,
        },
    )
    visit.status = V.DISPATCHED
    visit.save(update_fields=["status"])


def dispatch_tomorrow():
    tomorrow = timezone.localdate() + timedelta(days=1)
    count = 0
    for visit in Visit.objects.select_related("subscription__plan").filter(
        date=tomorrow, status=V.SCHEDULED, subscription__status=S.ACTIVE
    ):
        with transaction.atomic():
            dispatch(visit)
        count += 1
    return count


JOB_TO_VISIT = {"assigned": V.DISPATCHED, "accepted": V.DISPATCHED, "open": V.DISPATCHED, "on_the_way": V.IN_PROGRESS,
                "working": V.IN_PROGRESS, "completed": V.COMPLETED, "cancelled": V.CANCELLED}


@transaction.atomic
def apply_job_status(payload):
    if payload.get("source") != "subscription_visit":
        return
    visit = Visit.objects.select_for_update().select_related("subscription").filter(pk=payload["source_id"]).first()
    new = JOB_TO_VISIT.get(payload["status"])
    if visit is None or new is None or visit.status in (V.COMPLETED, V.SKIPPED):
        return
    visit.status = new
    if payload.get("provider_id"):
        visit.provider_id, visit.provider_name = payload["provider_id"], payload.get("provider_name", "")
    if new == V.COMPLETED:
        visit.completed_at = timezone.now()
        sub = visit.subscription
        if not sub.preferred_provider_id and visit.provider_id:
            sub.preferred_provider_id, sub.preferred_provider_name = visit.provider_id, visit.provider_name
            sub.save(update_fields=["preferred_provider_id", "preferred_provider_name"])
    visit.save()


def mark_paid(payload):
    if payload.get("purpose") != "subscription":
        return
    with transaction.atomic():
        sub = Subscription.objects.select_for_update().filter(pk=payload["reference_id"]).first()
        if sub is None or sub.paid:
            return
        sub.paid = True
        if sub.status == S.PENDING_PAYMENT:
            sub.status = S.ACTIVE
        sub.save(update_fields=["paid", "status"])
        publish_status(sub)


def daily_housekeeping():
    """Expire finished periods, resume paused ones, renew, and send renewal reminders."""
    today = timezone.localdate()
    for sub in Subscription.objects.filter(status=S.PAUSED, paused_until__lte=today):
        resume(sub)
    remind_on = today + timedelta(days=settings.RENEWAL_REMINDER_DAYS)
    for sub in Subscription.objects.filter(status=S.ACTIVE, end_date=remind_on, auto_renew=True):
        events.publish("subscription.renewal_reminder", {"subscription_id": sub.id, "user_id": sub.user_id, "end_date": sub.end_date.isoformat()})
    renewed = 0
    for sub in Subscription.objects.filter(status__in=[S.ACTIVE, S.PAUSED], end_date__lt=today + timedelta(days=1)).select_related("plan"):
        if sub.auto_renew and not hasattr(sub, "renewal") and sub.end_date == today:
            renew(sub)
            renewed += 1
        if sub.end_date < today:
            sub.status = S.EXPIRED
            sub.save(update_fields=["status"])
            publish_status(sub)
    return renewed


def renew(sub, plan=None):
    if hasattr(sub, "renewal"):
        raise ValidationError({"subscription": "Already renewed."})
    data = {
        "plan": plan or sub.next_plan or sub.plan,
        "duration_days": sub.duration_days,
        "home_size": sub.home_size,
        "preferred_weekday": sub.preferred_weekday,
        "slot": sub.slot,
        "start_date": max(sub.end_date + timedelta(days=1), timezone.localdate() + timedelta(days=1)),
        "area_id": sub.area_id,
        "area_name": sub.area_name,
        "address_line": sub.address_line,
        "latitude": sub.latitude,
        "longitude": sub.longitude,
        "diet": sub.diet,
        "prefer_female": sub.required_gender == "female",
        "addons": sub.addons,
        "members": sub.members,
        "prepaid_months": sub.prepaid_months,
        "payment_method": sub.payment_method,
        "agreement_id": sub.agreement_id,
        "auto_renew": sub.auto_renew,
    }
    new = create(sub.user_id, sub.customer_name, sub.customer_phone, data, renewed_from=sub)
    with transaction.atomic():
        sub.credit = max(sub.credit - new.credit_applied, Decimal("0"))
        sub.save(update_fields=["credit"])
    events.publish("subscription.renewed", {"subscription_id": new.id, "previous_id": sub.id, "user_id": sub.user_id, "amount": str(new.amount_due)})
    return new
