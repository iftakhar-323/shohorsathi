from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from shohor_common import events, roles

from .models import HomeReminder, User


@shared_task(name="auth.provider.approved")
def provider_approved(payload):
    User.objects.filter(pk=payload["user_id"], role=roles.CUSTOMER).update(role=roles.PROVIDER)


@shared_task(name="auth.provider.suspended")
def provider_suspended(payload):
    User.objects.filter(pk=payload["user_id"], role=roles.PROVIDER).update(role=roles.CUSTOMER)


# Customers hear about home upkeep this many days before it is due.
REMINDER_LEAD_DAYS = 3


@shared_task(name="auth.home_reminders_due")
def home_reminders_due():
    today = timezone.localdate()
    due = HomeReminder.objects.filter(is_completed=False, notified_on__isnull=True, due_date__lte=today + timedelta(days=REMINDER_LEAD_DAYS))
    for r in due.select_related("home"):
        events.publish("home.reminder_due", {
            "user_id": r.home.user_id, "home_id": r.home_id, "title_bn": r.title_bn, "title_en": r.title_en,
            "due_date": r.due_date.isoformat(), "service_slug": r.recommended_service_slug,
        })
        HomeReminder.objects.filter(pk=r.pk).update(notified_on=today)
