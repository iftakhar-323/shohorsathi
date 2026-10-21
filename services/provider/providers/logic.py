"""Job lifecycle, provider verification and earnings."""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from shohor_common import events, internal

from .models import Earning, Job, JobLog, Payout, Provider

S = Job.Status
# status -> statuses a provider may move the job to
PROVIDER_FLOW = {
    S.ACCEPTED: {S.ON_THE_WAY},
    S.ON_THE_WAY: {S.WORKING},
    S.WORKING: {S.COMPLETED},
}
JOB_FIELDS = [
    "booking_id", "user_id", "title", "service_slug", "category_slug", "area_id", "area_name", "address_line",
    "latitude", "longitude", "customer_name", "customer_phone", "scheduled_date", "slot", "amount", "is_emergency",
    "description", "photo_urls", "preferred_provider_id", "commission_override",
]
SLOT_END_HOUR = {"09-11": 11, "11-13": 13, "14-16": 16, "16-18": 18, "18-20": 20, "20-22": 22}


def publish_status(job, note=""):
    p = job.provider
    events.publish(
        "job.status_changed",
        {
            "job_id": job.id,
            "source": job.source,
            "source_id": job.source_id,
            "user_id": job.user_id,
            "status": job.status,
            "provider_id": p.user_id if p else None,
            "provider_name": p.full_name if p else "",
            "provider_phone": p.phone if p else "",
            "note": note,
        },
    )


def set_status(job, status, note="", actor="system"):
    job.status = status
    job.save()
    JobLog.objects.create(job=job, status=status, note=note, actor=actor)
    publish_status(job, note)


def available_jobs(provider):
    return Job.objects.filter(
        status=S.OPEN,
        area_id__in=provider.area_ids,
        category_slug__in=provider.skills,
    )


# ---- events from other services -------------------------------------------------------------

@transaction.atomic
def create_job(payload):
    data = {k: payload.get(k) for k in JOB_FIELDS if k in payload}
    data.setdefault("booking_id", payload.get("booking_id"))
    job, created = Job.objects.get_or_create(source=payload["source"], source_id=payload["source_id"], defaults=data)
    if not created:
        return job
    JobLog.objects.create(job=job, status=S.OPEN, note="Job created")
    preferred = Provider.objects.filter(user_id=job.preferred_provider_id, status=Provider.Status.APPROVED).first()
    if preferred:
        job.provider = preferred
        set_status(job, S.ASSIGNED, "Assigned to the previous provider")
    elif job.is_emergency:
        events.publish(
            "emergency.raised",
            {
                "job_id": job.id,
                "title": job.title,
                "area_id": job.area_id,
                "provider_user_ids": list(
                    available_jobs_providers(job).filter(is_online=True).values_list("user_id", flat=True)[:20]
                ),
            },
        )
    return job


def available_jobs_providers(job):
    return Provider.objects.filter(
        status=Provider.Status.APPROVED, area_ids__contains=[job.area_id], skills__contains=[job.category_slug]
    )


@transaction.atomic
def cancel_from_source(payload):
    job = Job.objects.select_for_update().filter(source=payload["source"], source_id=payload["source_id"]).first()
    if job and job.status not in (S.COMPLETED, S.CANCELLED):
        set_status(job, S.CANCELLED, "Cancelled by customer")


def reschedule_from_source(payload):
    job = Job.objects.filter(source=payload["source"], source_id=payload["source_id"]).first()
    if job and job.status not in (S.COMPLETED, S.CANCELLED):
        job.scheduled_date, job.slot = payload["scheduled_date"], payload["slot"]
        job.save(update_fields=["scheduled_date", "slot", "updated_at"])
        JobLog.objects.create(job=job, status="rescheduled", note=f"{job.scheduled_date} {job.slot}")


# ---- provider actions ---------------------------------------------------------------------

def _locked(job):
    return Job.objects.select_for_update().get(pk=job.pk)


@transaction.atomic
def accept(job, provider):
    job = _locked(job)
    if job.status == S.OPEN:
        if job.area_id not in provider.area_ids or job.category_slug not in provider.skills:
            raise ValidationError({"job": "This job is outside your areas or skills."})
    elif not (job.status == S.ASSIGNED and job.provider_id == provider.id):
        raise ValidationError({"job": "This job is no longer available."})
    job.provider = provider
    job.accepted_at = timezone.now()
    set_status(job, S.ACCEPTED, actor="provider")
    return job


@transaction.atomic
def reject(job, provider):
    job = _locked(job)
    if job.provider_id != provider.id or job.status not in (S.ASSIGNED, S.ACCEPTED):
        raise ValidationError({"job": "You can only release jobs assigned to you before starting."})
    job.provider = None
    job.accepted_at = None
    set_status(job, S.OPEN, "Released by provider", actor="provider")
    return job


@transaction.atomic
def advance(job, provider, status, arrival_code="", note="", photos=None, checklist=None):
    job = _locked(job)
    if job.provider_id != provider.id:
        raise ValidationError({"job": "This job is not assigned to you."})
    if status not in PROVIDER_FLOW.get(job.status, set()):
        raise ValidationError({"status": f"Cannot move from {job.status} to {status}."})
    if status == S.WORKING:
        if job.booking_id and job.source in (Job.Source.BOOKING, Job.Source.WARRANTY):
            check = internal.get("order", f"/api/internal/bookings/{job.booking_id}/verify-arrival/", code=arrival_code)
            if not check or not check.get("ok"):
                raise ValidationError({"arrival_code": "Wrong arrival code. Ask the customer for the 4-digit code."})
        job.started_at = timezone.now()
        if photos:
            job.before_photos = photos
    if status == S.COMPLETED:
        job.completed_at = timezone.now()
        if photos:
            job.after_photos = photos
        if checklist is not None:
            job.checklist = checklist
        if note:
            job.provider_note = note
    set_status(job, status, note, actor="provider")
    if status == S.COMPLETED:
        record_completion(job)
    return job


def record_completion(job):
    provider = job.provider
    provider.jobs_completed += 1
    end_hour = SLOT_END_HOUR.get(job.slot)
    local = timezone.localtime(job.started_at) if job.started_at else None
    if local and end_hour and local.date() <= job.scheduled_date and local.hour < end_hour:
        provider.jobs_on_time += 1
    provider.save(update_fields=["jobs_completed", "jobs_on_time"])

    gross = job.amount
    if job.commission_override is not None:
        commission = job.commission_override
    else:
        commission = (gross * Decimal(settings.PROVIDER_COMMISSION_PERCENT) / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)
    bonus = Decimal(settings.PROVIDER_HIGH_RATING_BONUS) if provider.rating_count >= 10 and provider.rating_avg >= Decimal("4.8") else Decimal("0")
    Earning.objects.create(provider=provider, job=job, gross=gross, commission=commission, bonus=bonus, net=gross - commission + bonus)
    events.publish(
        "job.completed",
        {"job_id": job.id, "source": job.source, "source_id": job.source_id, "provider_user_id": provider.user_id,
         "user_id": job.user_id, "amount": str(gross), "commission": str(commission)},
    )


# ---- admin actions ------------------------------------------------------------------------

@transaction.atomic
def assign(job, provider):
    job = _locked(job)
    if provider.status != Provider.Status.APPROVED:
        raise ValidationError({"provider_id": "Provider is not approved."})
    if job.status not in (S.OPEN, S.ASSIGNED, S.ACCEPTED):
        raise ValidationError({"job": "Job already started or closed."})
    job.provider = provider
    set_status(job, S.ASSIGNED, f"Assigned to {provider.full_name}", actor="admin")
    return job


def suggest_providers(job, limit=5):
    """Smart matching: approved providers in the area with the skill, online first, then trust and rating."""
    candidates = list(available_jobs_providers(job))
    busy = set(
        Job.objects.filter(scheduled_date=job.scheduled_date, slot=job.slot, status__in=[S.ASSIGNED, S.ACCEPTED, S.ON_THE_WAY, S.WORKING])
        .values_list("provider_id", flat=True)
    )
    free = [p for p in candidates if p.id not in busy]
    free.sort(key=lambda p: (not p.is_online, -p.trust_score, -float(p.rating_avg)))
    return free[:limit]


@transaction.atomic
def review_provider(provider, decision, reason=""):
    if decision == "approve":
        provider.status = Provider.Status.APPROVED
        provider.approved_at = timezone.now()
        provider.rejection_reason = ""
        events.publish("provider.approved", {"user_id": provider.user_id, "provider_id": provider.id})
    elif decision == "reject":
        provider.status = Provider.Status.REJECTED
        provider.rejection_reason = reason
    elif decision == "suspend":
        provider.status = Provider.Status.SUSPENDED
        provider.is_online = False
        provider.rejection_reason = reason
        events.publish("provider.suspended", {"user_id": provider.user_id, "provider_id": provider.id})
    provider.save()
    return provider


# ---- earnings & payouts -------------------------------------------------------------------

def earnings_summary(provider):
    def total(**f):
        return str(provider.earnings.filter(**f).aggregate(s=Sum("net"))["s"] or 0)

    week_start = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
    return {
        "pending": total(status=Earning.Status.PENDING),
        "in_payout": total(status=Earning.Status.IN_PAYOUT),
        "paid": total(status=Earning.Status.PAID),
        "this_week": total(created_at__date__gte=week_start),
        "commission_total": str(provider.earnings.aggregate(s=Sum("commission"))["s"] or 0),
        "jobs_completed": provider.jobs_completed,
        "rating_avg": str(provider.rating_avg),
        "trust_score": provider.trust_score,
    }


@transaction.atomic
def request_payout(provider):
    if not provider.payout_method or not provider.payout_account:
        raise ValidationError({"payout": "Add your bKash or Nagad number in your profile first."})
    pending = provider.earnings.select_for_update().filter(status=Earning.Status.PENDING)
    amount = pending.aggregate(s=Sum("net"))["s"] or Decimal("0")
    if amount <= 0:
        raise ValidationError({"payout": "Nothing to pay out yet."})
    payout = Payout.objects.create(
        provider=provider, amount=amount, method=provider.payout_method, account=provider.payout_account
    )
    pending.update(status=Earning.Status.IN_PAYOUT, payout=payout)
    return payout


@transaction.atomic
def mark_payout_paid(payout, reference):
    if payout.status != Payout.Status.REQUESTED:
        raise ValidationError({"payout": "Payout already handled."})
    payout.status, payout.reference, payout.paid_at = Payout.Status.PAID, reference, timezone.now()
    payout.save()
    payout.earnings.update(status=Earning.Status.PAID)
    return payout


def weekly_payouts():
    created = 0
    with_pending = Provider.objects.filter(earnings__status=Earning.Status.PENDING).exclude(payout_account="").distinct()
    for provider in with_pending:
        try:
            request_payout(provider)
            created += 1
        except ValidationError:
            pass
    return created


def apply_review(payload):
    """A customer rated a job: keep the provider's running average."""
    provider = Provider.objects.filter(user_id=payload["provider_user_id"]).first()
    if provider is None:
        return
    total = provider.rating_avg * provider.rating_count + Decimal(payload["rating"])
    provider.rating_count += 1
    provider.rating_avg = (total / provider.rating_count).quantize(Decimal("0.01"))
    badges = set(provider.badges)
    if provider.rating_count >= 10 and provider.rating_avg >= Decimal("4.8"):
        badges.add("top_rated")
    if provider.jobs_completed >= 50:
        badges.add("50_jobs")
    provider.badges = sorted(badges)
    provider.save(update_fields=["rating_avg", "rating_count", "badges"])


def search_q(qs, q):
    return qs.filter(Q(full_name__icontains=q) | Q(phone__contains=q)) if q else qs
