"""Dhap 9 insights over the event facts: demand forecast, churn risk and fraud signals.

All three are deliberately simple and explainable (averages, ratios, thresholds) so ops can see why a number came
out the way it did; each result says what it is based on.
"""
import math
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
from statistics import median

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .logic import city_area_ids
from .models import Fact

HISTORY_WEEKS = 8


def _bookings(city=None, area=None):
    qs = Fact.objects.filter(event="booking.created")
    if city:
        qs = qs.filter(area_id__in=city_area_ids(city))
    if area:
        qs = qs.filter(area_id=area)
    return qs


def forecast(city=None, area=None, days=7):
    """Bookings expected per category for each of the next `days` days.

    Same-weekday average over the last eight weeks, scaled by the recent trend (last 14 days vs the 14 before,
    clipped to 0.5–2×). `providers_needed` divides by how many jobs one provider does in a day.
    """
    today = timezone.localdate()
    start = today - timedelta(weeks=HISTORY_WEEKS)
    rows = (_bookings(city, area).filter(occurred_at__date__gte=start, occurred_at__date__lt=today).exclude(category="")
            .annotate(day=TruncDate("occurred_at")).values("category", "day").annotate(n=Count("id")))
    counts = defaultdict(Counter)
    for r in rows:
        counts[r["category"]][r["day"]] += r["n"]

    per_provider = settings.JOBS_PER_PROVIDER_DAY
    result = []
    for category, by_day in counts.items():
        recent = sum(n for d, n in by_day.items() if d >= today - timedelta(days=14))
        before = sum(n for d, n in by_day.items() if today - timedelta(days=28) <= d < today - timedelta(days=14))
        trend = min(max((recent + 1) / (before + 1), 0.5), 2.0)
        upcoming = []
        for ahead in range(1, days + 1):
            day = today + timedelta(days=ahead)
            same_weekday = [by_day.get(day - timedelta(weeks=w), 0) for w in range(1, HISTORY_WEEKS + 1)]
            expected = round(sum(same_weekday) / HISTORY_WEEKS * trend, 1)
            upcoming.append({"date": day.isoformat(), "expected": expected, "providers_needed": math.ceil(expected / per_provider)})
        result.append({"category": category, "trend": round(trend, 2), "last_14_days": recent, "days": upcoming,
                       "week_total": round(sum(d["expected"] for d in upcoming), 1)})
    return sorted(result, key=lambda c: -c["week_total"])


def churn(city=None, limit=100):
    """Customers who have gone quiet compared with how often they used to order.

    risk score = days since the last order ÷ the customer's usual gap between orders (at least 14 days);
    one-time customers count after 45 days. Customers gone more than a year are treated as lost, not at risk.
    """
    qs = Fact.objects.filter(event="order.placed").exclude(user_id=None)
    if city:
        qs = qs.filter(area_id__in=city_area_ids(city))
    now = timezone.now()
    orders = defaultdict(list)
    value = defaultdict(Decimal)
    for user_id, at, amount in qs.values_list("user_id", "occurred_at", "amount").order_by("occurred_at"):
        orders[user_id].append(at)
        value[user_id] += amount

    at_risk = []
    for user_id, times in orders.items():
        since = (now - times[-1]).days
        if since > 365:
            continue
        gaps = [(b - a).days for a, b in zip(times, times[1:])]
        usual = max(median(gaps), 14) if gaps else None
        if usual:
            score = since / usual
            if score < 2:
                continue
        else:
            if since < 45:
                continue
            score = since / 30
        at_risk.append({
            "user_id": user_id, "orders": len(times), "value": str(value[user_id]), "last_order": times[-1].isoformat(),
            "days_since": since, "usual_gap_days": usual, "score": round(score, 1), "risk": "high" if score >= 3 else "medium",
        })
    return sorted(at_risk, key=lambda c: (-Decimal(c["value"]), -c["score"]))[:limit]


def fraud(days=30):
    """Patterns worth a human look; none of them blocks anyone on its own."""
    since = timezone.now() - timedelta(days=days)
    facts = Fact.objects.filter(occurred_at__gte=since)
    flags = []

    # 1. Order-and-cancel abuse: ties up providers and slots.
    status = (facts.filter(event="order.status_changed").exclude(user_id=None).values("user_id")
              .annotate(cancelled=Count("id", filter=Q(status="cancelled")), done=Count("id", filter=Q(status="completed"))))
    for r in status:
        if r["cancelled"] >= 3 and r["cancelled"] >= r["done"]:
            flags.append({"kind": "cancel_abuse", "severity": "medium", "user_ids": [r["user_id"]],
                          "detail": f"{r['cancelled']} cancelled vs {r['done']} completed orders in {days} days"})

    # 2. Order bursts: many orders inside one hour (scripted or a stolen account).
    placed = defaultdict(list)
    for user_id, at in facts.filter(event="order.placed").exclude(user_id=None).values_list("user_id", "occurred_at").order_by("occurred_at"):
        placed[user_id].append(at)
    for user_id, times in placed.items():
        burst = max((sum(1 for t in times[i:] if t - start <= timedelta(hours=1)) for i, start in enumerate(times)), default=0)
        if burst >= 5:
            flags.append({"kind": "order_burst", "severity": "high", "user_ids": [user_id], "detail": f"{burst} orders within one hour"})

    # 3. Many accounts booking to the same spot (~10 m): referral or first-order-discount farming.
    spots = defaultdict(set)
    for user_id, lat, lng in facts.filter(event="booking.created").exclude(latitude=None).exclude(user_id=None).values_list("user_id", "latitude", "longitude"):
        spots[(round(float(lat), 4), round(float(lng), 4))].add(user_id)
    for (lat, lng), users in spots.items():
        if len(users) >= 4:
            flags.append({"kind": "shared_location", "severity": "medium", "user_ids": sorted(users),
                          "detail": f"{len(users)} accounts booked to {lat}, {lng}", "latitude": lat, "longitude": lng})

    # 4. Big cash-on-delivery first orders: the usual fake-order pattern for COD.
    first = dict(Fact.objects.filter(event="order.placed", user_id__in=list(placed)).values("user_id").annotate(n=Count("id")).values_list("user_id", "n"))
    for f in facts.filter(event="order.placed", category="cod", amount__gte=settings.FRAUD_BIG_COD_AMOUNT):
        if first.get(f.user_id) == 1:
            flags.append({"kind": "big_first_cod", "severity": "low", "user_ids": [f.user_id], "detail": f"first order ৳{f.amount} cash on delivery",
                          "ref": f.ref})

    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(flags, key=lambda f: order[f["severity"]])


def revenue(days=30, city=None):
    """Where the platform's own income comes from: commission on jobs and sponsored listings."""
    since = timezone.now() - timedelta(days=days)
    qs = Fact.objects.filter(occurred_at__gte=since)
    if city:
        qs = qs.filter(area_id__in=city_area_ids(city))
    commission = qs.filter(event="job.completed").aggregate(s=Sum("commission"))["s"] or Decimal("0")
    sponsored = qs.filter(event="listing.sponsored").aggregate(s=Sum("amount"))["s"] or Decimal("0")
    return {"days": days, "commission": str(commission), "sponsored_listings": str(sponsored), "total": str(commission + sponsored)}
