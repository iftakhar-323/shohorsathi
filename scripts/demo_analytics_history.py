# Synthetic 8-week history for the demo analytics tabs (forecast, churn, fraud). Run inside the analytics container:
#   python manage.py shell -c "exec(open('/tmp/demo_history.py').read())"   (scripts/seed_demo.py does this)
# Fake users have ids 9000+ so they are easy to tell apart from real accounts.
import random
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from analytics_app.models import Fact

random.seed(7)
now = timezone.now()
AREAS = [(1, "ধানমন্ডি", 23.7465, 90.3760), (2, "মিরপুর", 23.8069, 90.3686), (3, "গুলশান", 23.7925, 90.4078), (4, "উত্তরা", 23.8759, 90.3795)]
# category: (title, price, bookings on a weekday, extra on Fri/Sat, growth per week)
CATS = {"ac": ("এসি ক্লিনিং", 800, 3, 4, 0.12), "cleaning": ("হোম ডিপ ক্লিন", 2500, 2, 5, 0.04), "electrical": ("ইলেকট্রিশিয়ান ভিজিট", 300, 4, 2, 0.0),
        "plumbing": ("প্লাম্বার ভিজিট", 300, 2, 1, 0.0), "pest-control": ("তেলাপোকা নিয়ন্ত্রণ", 1500, 1, 1, 0.08)}
rows = []
for days_ago in range(56, 0, -1):
    at = now - timedelta(days=days_ago, hours=random.randint(0, 10))
    week = (56 - days_ago) // 7
    for cat, (title, price, base, weekend, growth) in CATS.items():
        n = base + (weekend if at.weekday() in (4, 5) else 0)
        n = max(0, round(n * (1 + growth) ** week + random.uniform(-1, 1)))
        for _ in range(n):
            aid, aname, lat, lng = random.choice(AREAS)
            rows.append(Fact(event="booking.created", user_id=9000 + random.randint(1, 60), area_id=aid, area_name=aname, category=cat, title=title,
                             amount=price, latitude=Decimal(f"{lat + random.uniform(-0.01, 0.01):.6f}"), longitude=Decimal(f"{lng + random.uniform(-0.01, 0.01):.6f}"),
                             ref="demo", payload={"demo": True}))
            rows[-1]._at = at
# customers: loyal ones keep ordering every ~10 days, some stopped 30-60 days ago (churn risk)
for u in range(1, 41):
    gap = random.choice([7, 10, 14])
    stop = random.choice([0, 0, 0, 35, 50]) if u % 3 == 0 else 0
    d = 120
    while d > stop:
        aid, aname, _, _ = random.choice(AREAS)
        total = random.choice([300, 800, 1500, 2500])
        f = Fact(event="order.placed", user_id=9000 + u, area_id=aid, area_name=aname, category="cod", amount=total, ref="demo", payload={"demo": True})
        f._at = now - timedelta(days=d)
        rows.append(f)
        c = Fact(event="job.completed", amount=total, commission=Decimal(total) * Decimal("0.15"), category="booking", ref="demo", payload={"demo": True})
        c._at = f._at + timedelta(hours=5)
        rows.append(c)
        d -= gap + random.randint(-2, 2)
# a few fraud-looking patterns
for i in range(4):
    f = Fact(event="order.status_changed", user_id=9101, status="cancelled", amount=500, ref="demo", payload={"demo": True}); f._at = now - timedelta(days=i * 3 + 1); rows.append(f)
for u in (9201, 9202, 9203, 9204, 9205):
    f = Fact(event="booking.created", user_id=u, category="cleaning", title="হোম ডিপ ক্লিন", amount=2500, latitude=Decimal("23.751200"), longitude=Decimal("90.393400"),
             area_id=1, area_name="ধানমন্ডি", ref="demo", payload={"demo": True}); f._at = now - timedelta(days=u - 9200); rows.append(f)
f = Fact(event="order.placed", user_id=9301, category="cod", amount=28000, area_id=3, area_name="গুলশান", ref="demo", payload={"demo": True}); f._at = now - timedelta(days=2); rows.append(f)

Fact.objects.filter(ref="demo").delete()
created = Fact.objects.bulk_create(rows)
for f, r in zip(created, rows):
    f.occurred_at = r._at
Fact.objects.bulk_update(created, ["occurred_at"], batch_size=1000)
print(f"analytics history: {len(created)} synthetic facts over 8 weeks")
