from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Min, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from shohor_common import internal

from .models import Fact


def record(event, p):
    """Map each event's payload onto the reporting columns."""
    row = {"event": event, "user_id": p.get("user_id"), "payload": p, "area_id": p.get("area_id"), "area_name": p.get("area_name", "")}
    if event == "order.placed":
        row.update(amount=p.get("total", 0), ref=f"order:{p['order_id']}", category=p.get("payment_method", ""))
    elif event == "order.status_changed":
        if p["status"] not in ("completed", "cancelled"):
            return None
        row.update(status=p["status"], amount=p.get("total", 0), ref=f"order:{p['order_id']}")
    elif event == "booking.created":
        row.update(category=p.get("category_slug", ""), title=p.get("title", ""), amount=p.get("amount", 0),
                   latitude=p.get("latitude"), longitude=p.get("longitude"), ref=f"{p['source']}:{p['source_id']}",
                   status="emergency" if p.get("is_emergency") else "")
    elif event == "job.status_changed":
        if p["status"] != "completed":
            return None
        row.update(status="completed", category=p.get("source", ""), ref=f"job:{p['job_id']}")
    elif event == "job.completed":
        row.update(amount=p.get("amount", 0), commission=p.get("commission", 0), category=p.get("source", ""), ref=f"job:{p['job_id']}")
    elif event in ("subscription.created", "subscription.renewed"):
        row.update(amount=p.get("amount", 0), category=p.get("category", ""), title=p.get("plan", ""), ref=f"subscription:{p['subscription_id']}")
    elif event == "payment.succeeded":
        row.update(amount=p.get("amount", 0), category=p.get("purpose", ""), ref=f"payment:{p['payment_id']}")
    elif event == "listing.sponsored":
        row.update(amount=p.get("fee", 0), category=p.get("item_type", ""), title=p.get("name", ""), ref=f"{p.get('item_type')}:{p.get('slug')}")
    elif event == "issue.status_changed":
        row.update(status=p["status"], ref=f"issue:{p['issue_id']}")
    else:
        return None
    for k in ("latitude", "longitude"):
        row[k] = row.get(k) or None
    return Fact.objects.create(**row)


def city_area_ids(city):
    areas = internal.get("auth", "/api/areas/", city=city) or []
    return [a["id"] for a in areas]


def scope(days, city=None):
    since = timezone.now() - timedelta(days=days)
    qs = Fact.objects.filter(occurred_at__gte=since)
    if city:
        qs = qs.filter(area_id__in=city_area_ids(city))
    return qs, since


def total(qs, field="amount"):
    return qs.aggregate(s=Sum(field))["s"] or Decimal("0")


def summary(days=30, city=None):
    qs, since = scope(days, city)
    placed = qs.filter(event="order.placed")
    completed = qs.filter(event="order.status_changed", status="completed")
    bookings = qs.filter(event="booking.created")
    buyers = set(placed.values_list("user_id", flat=True))
    first_orders = dict(Fact.objects.filter(event="order.placed", user_id__in=buyers).values("user_id").annotate(first=Min("occurred_at")).values_list("user_id", "first"))
    new = sum(1 for u in buyers if first_orders.get(u) and first_orders[u] >= since)
    daily = (placed.annotate(day=TruncDate("occurred_at")).values("day").annotate(orders=Count("id"), value=Sum("amount")).order_by("day"))
    return {
        "days": days,
        "gmv": str(total(placed)),
        "revenue_completed": str(total(completed)),
        "commission": str(total(qs.filter(event="job.completed"), "commission")),
        "orders": placed.count(),
        "orders_completed": completed.count(),
        "orders_cancelled": qs.filter(event="order.status_changed", status="cancelled").count(),
        "bookings": bookings.count(),
        "emergency_bookings": bookings.filter(status="emergency").count(),
        "subscriptions_new": qs.filter(event="subscription.created").count(),
        "subscriptions_renewed": qs.filter(event="subscription.renewed").count(),
        "subscription_value": str(total(qs.filter(event__in=["subscription.created", "subscription.renewed"]))),
        "customers_new": new,
        "customers_returning": len(buyers) - new,
        "issues_resolved": qs.filter(event="issue.status_changed", status="resolved").values("ref").distinct().count(),
        "top_services": list(bookings.exclude(title="").values("title").annotate(n=Count("id"), value=Sum("amount")).order_by("-n")[:8]),
        "top_categories": list(bookings.exclude(category="").values("category").annotate(n=Count("id")).order_by("-n")[:8]),
        "by_area": list(qs.filter(event__in=["booking.created", "order.placed"]).exclude(area_id=None).values("area_id", "area_name").annotate(n=Count("id")).order_by("-n")[:15]),
        "daily": [{"day": d["day"].isoformat(), "orders": d["orders"], "value": str(d["value"] or 0)} for d in daily],
    }


def heatmap(days=30, city=None):
    """Booking demand, bucketed to ~100 m cells."""
    qs, _ = scope(days, city)
    cells = {}
    for lat, lng in qs.filter(event="booking.created").exclude(latitude=None).values_list("latitude", "longitude"):
        key = (round(float(lat), 3), round(float(lng), 3))
        cells[key] = cells.get(key, 0) + 1
    return [{"lat": k[0], "lng": k[1], "n": n} for k, n in sorted(cells.items(), key=lambda kv: -kv[1])][:500]
