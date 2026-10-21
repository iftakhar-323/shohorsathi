"""City-partnership reports: the public transparency dashboard and the CSV feed each authority downloads.

Nothing here carries the reporter's name, phone or user id.
"""
import csv
import io
from datetime import timedelta
from statistics import median

from django.db.models import Count, Q
from django.utils import timezone
from shohor_common import internal

from .models import Issue

I = Issue.Status
OPEN = [I.REPORTED, I.FORWARDED, I.IN_PROGRESS]
FEED_COLUMNS = ["id", "category", "title", "description", "landmark", "area_name", "latitude", "longitude", "status", "upvotes",
                "reported_at", "resolved_at", "photo_urls", "link"]


def city_area_ids(city):
    return [a["id"] for a in internal.get("auth", "/api/areas/", city=city) or []]


def _days_to_resolve(issues):
    days = [(i.resolved_at - i.created_at).total_seconds() / 86400 for i in issues if i.resolved_at]
    return round(median(days), 1) if days else None


def report(days=90, city=None):
    since = timezone.now() - timedelta(days=days)
    qs = Issue.objects.filter(created_at__gte=since).exclude(status=I.REJECTED)
    if city:
        qs = qs.filter(area_id__in=city_area_ids(city))
    resolved = list(qs.filter(status=I.RESOLVED).only("created_at", "resolved_at", "category", "authority_id"))
    total = qs.count()

    by_category = []
    for row in qs.values("category").annotate(n=Count("id"), done=Count("id", filter=Q(status=I.RESOLVED))).order_by("-n"):
        by_category.append({**row, "median_days": _days_to_resolve(r for r in resolved if r.category == row["category"])})

    by_authority = []
    rows = (qs.exclude(authority=None).values("authority_id", "authority__name_bn", "authority__name_en")
            .annotate(n=Count("id"), done=Count("id", filter=Q(status=I.RESOLVED)), open=Count("id", filter=Q(status__in=OPEN))).order_by("-n"))
    for row in rows:
        by_authority.append({
            "name_bn": row["authority__name_bn"], "name_en": row["authority__name_en"], "assigned": row["n"], "resolved": row["done"],
            "open": row["open"], "median_days": _days_to_resolve(r for r in resolved if r.authority_id == row["authority_id"]),
        })

    months = []
    today = timezone.localdate().replace(day=1)
    for back in range(5, -1, -1):
        start = (today - timedelta(days=back * 31)).replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        months.append({
            "month": start.isoformat()[:7],
            "reported": Issue.objects.filter(created_at__date__gte=start, created_at__date__lt=end).exclude(status=I.REJECTED).count(),
            "resolved": Issue.objects.filter(resolved_at__date__gte=start, resolved_at__date__lt=end).count(),
        })

    return {
        "days": days,
        "reported": total,
        "resolved": len(resolved),
        "open": qs.filter(status__in=OPEN).count(),
        "resolution_rate": round(len(resolved) * 100 / total) if total else 0,
        "median_days_to_resolve": _days_to_resolve(resolved),
        "by_category": by_category,
        "by_authority": by_authority,
        "open_hotspots": list(qs.filter(status__in=OPEN).values("area_id", "area_name").annotate(n=Count("id")).order_by("-n")[:10]),
        "months": months,
    }


def feed_csv(issues, base_url):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(FEED_COLUMNS)
    for i in issues:
        writer.writerow([
            i.id, i.category, i.title, i.description, i.landmark, i.area_name, i.latitude, i.longitude, i.status, i.upvote_count,
            i.created_at.isoformat(), i.resolved_at.isoformat() if i.resolved_at else "", " ".join(f"{base_url}{u}" for u in i.photo_urls),
            f"{base_url}/issues/{i.id}",
        ])
    # Excel opens Bangla CSV correctly only with a byte-order mark.
    return "﻿" + out.getvalue()
