from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.core.management import call_command
from django.utils import timezone
from shohor_common.testing import auth_client

from subscriptions import logic
from subscriptions.models import StudentVerification, Subscription, Visit

TOMORROW = timezone.localdate() + timedelta(days=1)


@pytest.fixture(autouse=True)
def plans(db):
    call_command("seed_plans", verbosity=0)


@pytest.fixture
def customer():
    return auth_client("customer", user_id=7, name="Rahim", phone="01712345678")


def subscribe(client, **overrides):
    body = {"plan": "cleaning-premium", "duration_days": 30, "home_size": 2, "start_date": TOMORROW.isoformat(),
            "preferred_weekday": TOMORROW.weekday(), "slot": "09-11", "area_id": 3, "area_name": "Mirpur", "address_line": "Road 1"}
    return client.post("/api/subscriptions/", {**body, **overrides}, format="json")


def test_plans_public_and_priced():
    from rest_framework.test import APIClient

    plans = APIClient().get("/api/subscription-plans/?category=cleaning").data
    assert [p["slug"] for p in plans] == ["cleaning-basic", "cleaning-standard", "cleaning-premium"]
    assert len(plans[0]["prices"]) == 9  # 3 durations x 3 home sizes


def test_quote_prepay_discount(customer):
    one = customer.post("/api/subscriptions/quote/", {"plan": "cleaning-basic", "duration_days": 30, "home_size": 1}, format="json").data
    six = customer.post("/api/subscriptions/quote/", {"plan": "cleaning-basic", "duration_days": 30, "home_size": 1, "prepaid_months": 6}, format="json").data
    assert Decimal(six["total"]) == Decimal(one["total"]) * 6 * Decimal("0.9")


def test_student_discount_needs_approval(customer):
    body = {"plan": "meal-student-saver", "duration_days": 30}
    before = customer.post("/api/subscriptions/quote/", body, format="json").data
    StudentVerification.objects.create(user_id=7, institution="DU", id_card_url="/x", status="approved")
    after = customer.post("/api/subscriptions/quote/", body, format="json").data
    assert after["student_discount"] and Decimal(after["total"]) == Decimal(before["total"]) * Decimal("0.9")


def test_premium_cleaning_schedule(customer, captured_events):
    res = subscribe(customer)
    assert res.status_code == 201, res.data
    sub = Subscription.objects.get()
    kinds = list(sub.visits.values_list("kind", flat=True))
    assert kinds.count("visit") == 5 and kinds.count("deep_clean") == 1  # weekly over 30 days from the chosen weekday
    assert sub.status == "active" and sub.end_date == TOMORROW + timedelta(days=29)
    assert sum(v.value for v in sub.visits.all()) == pytest.approx(sub.price, abs=Decimal("1"))
    assert captured_events[-1][0] == "subscription.created"


def test_meal_plan_one_visit_per_meal(customer):
    subscribe(customer, plan="meal-standard", duration_days=7, home_size=0, diet="bangla")
    sub = Subscription.objects.get()
    assert sub.visits.count() == 14 and set(sub.visits.values_list("meal_type", flat=True)) == {"lunch", "dinner"}


def test_start_must_be_future(customer):
    assert subscribe(customer, start_date=timezone.localdate().isoformat()).status_code == 400


def test_skip_before_cutoff_gives_credit(customer):
    subscribe(customer, plan="meal-standard", duration_days=7, home_size=0)
    visit = Visit.objects.order_by("date").first()
    early = timezone.make_aware(datetime.combine(timezone.localdate(), datetime.min.time()))
    with mock.patch("django.utils.timezone.now", return_value=early):
        res = customer.patch(f"/api/subscriptions/visits/{visit.id}/skip/")
    assert res.status_code == 200 and res.data["status"] == "skipped"
    assert Subscription.objects.get().credit == visit.value


def test_skip_after_cutoff_rejected(customer):
    subscribe(customer, plan="meal-standard", duration_days=7, home_size=0)
    visit = Visit.objects.order_by("date").first()
    late = logic.cutoff_for(visit.date) + timedelta(minutes=1)
    with mock.patch("django.utils.timezone.now", return_value=late):
        assert customer.patch(f"/api/subscriptions/visits/{visit.id}/skip/").status_code == 400


def test_dispatch_and_same_cleaner(customer, captured_events):
    subscribe(customer)
    first = Visit.objects.filter(date=TOMORROW).first()
    assert logic.dispatch_tomorrow() >= 1
    event, payload = [e for e in captured_events if e[0] == "subscription.visit_due"][0]
    assert payload["visit_id"] == first.id and payload["category_slug"] == "cleaning" and payload["preferred_provider_id"] is None

    logic.apply_job_status({"source": "subscription_visit", "source_id": first.id, "status": "completed", "provider_id": 55, "provider_name": "Karim"})
    sub = Subscription.objects.get()
    assert sub.preferred_provider_id == 55
    later = sub.visits.filter(date__gt=TOMORROW).order_by("date").first()
    logic.dispatch(later)
    assert captured_events[-1][1]["preferred_provider_id"] == 55


def test_rate_and_reclean(customer, captured_events):
    subscribe(customer)
    visit = Visit.objects.filter(kind="visit").first()
    Visit.objects.filter(pk=visit.pk).update(status="completed", completed_at=timezone.now(), provider_id=55)
    res = customer.post(f"/api/subscriptions/visits/{visit.id}/rate/", {"rating": 2, "feedback": "Bathroom not cleaned"}, format="json")
    assert res.status_code == 200
    assert ("review.created", {"source": "subscription_visit", "source_id": visit.id, "user_id": 7, "provider_user_id": 55, "rating": 2, "comment": "Bathroom not cleaned"}) in captured_events
    redo = customer.post(f"/api/subscriptions/visits/{visit.id}/reclean/")
    assert redo.status_code == 201 and redo.data["status"] == "dispatched"
    assert customer.post(f"/api/subscriptions/visits/{visit.id}/reclean/").status_code == 400


def test_bad_meal_credited(customer):
    subscribe(customer, plan="meal-standard", duration_days=7, home_size=0)
    visit = Visit.objects.first()
    Visit.objects.filter(pk=visit.pk).update(status="completed", completed_at=timezone.now())
    customer.post(f"/api/subscriptions/visits/{visit.id}/rate/", {"rating": 1}, format="json")
    assert Subscription.objects.get().credit == visit.value


def test_pause_cancel_and_events(customer, captured_events):
    sub_id = subscribe(customer).data["id"]
    paused = customer.patch(f"/api/subscriptions/{sub_id}/pause/", {"until": (TOMORROW + timedelta(days=10)).isoformat()}, format="json")
    assert paused.data["status"] == "paused" and Decimal(paused.data["credit"]) > 0
    assert customer.patch(f"/api/subscriptions/{sub_id}/resume/").data["status"] == "active"
    v = Visit.objects.filter(status="scheduled").order_by("date").first()
    logic.dispatch(v)
    cancelled = customer.patch(f"/api/subscriptions/{sub_id}/cancel/").data
    assert cancelled["status"] == "cancelled"
    assert captured_events[-1][1]["cancelled_visit_ids"] == [v.id]


def test_online_payment_activates(customer):
    sub_id = subscribe(customer, payment_method="online").data["id"]
    assert Subscription.objects.get().status == "pending_payment"
    assert logic.dispatch_tomorrow() == 0
    logic.mark_paid({"purpose": "subscription", "reference_id": sub_id})
    sub = Subscription.objects.get()
    assert sub.status == "active" and sub.paid


def test_renewal_applies_credit_and_upgrade(customer, captured_events):
    sub_id = subscribe(customer, plan="cleaning-basic").data["id"]
    customer.patch(f"/api/subscriptions/{sub_id}/settings/", {"next_plan": "cleaning-standard"}, format="json")
    sub = Subscription.objects.get()
    sub.credit = Decimal("100")
    sub.save()
    with mock.patch("django.utils.timezone.localdate", return_value=sub.end_date):
        assert logic.daily_housekeeping() == 1
    new = Subscription.objects.exclude(pk=sub_id).get()
    assert new.plan.slug == "cleaning-standard" and new.credit_applied == 100 and new.start_date == sub.end_date + timedelta(days=1)
    assert Subscription.objects.get(pk=sub_id).credit == 0
    assert "subscription.renewed" in [e for e, _ in captured_events]


def test_group_plan_split(customer):
    members = [{"name": "A", "phone": "01711111111"}, {"name": "B", "phone": "01722222222"}, {"name": "C", "phone": "01733333333"}]
    q = customer.post("/api/subscriptions/quote/", {"plan": "meal-standard", "duration_days": 30, "members": members}, format="json").data
    assert Decimal(q["per_member"]) == (Decimal(q["total"]) / 3).quantize(Decimal("0.01"))


def test_privacy(customer):
    sub_id = subscribe(customer).data["id"]
    assert auth_client("customer", user_id=8).get(f"/api/subscriptions/{sub_id}/").status_code == 404
    assert customer.get("/api/admin/subscriptions/").status_code == 403


def test_bkash_auto_debit_renewal(customer, captured_events):
    with mock.patch("shohor_common.internal.post", return_value=(200, {"status": "held", "method": "bKash Auto-Debit"})):
        res = subscribe(customer, payment_method="bkash_auto", agreement_id="AGR-SUB-888")
        assert res.status_code == 201
        sub = Subscription.objects.get(pk=res.data["id"])
        assert sub.payment_method == "bkash_auto" and sub.agreement_id == "AGR-SUB-888"
        assert sub.status == "active" and sub.paid

        # Renew through daily housekeeping
        with mock.patch("django.utils.timezone.localdate", return_value=sub.end_date):
            assert logic.daily_housekeeping() == 1
        new = Subscription.objects.exclude(pk=sub.id).get()
        assert new.payment_method == "bkash_auto" and new.agreement_id == "AGR-SUB-888"
        assert new.status == "active" and new.paid

