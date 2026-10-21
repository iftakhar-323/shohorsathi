"""Trust & safety: SOS, live-job sharing, two-way ratings, review disputes, insurance, training, instant payouts."""
import secrets
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from shohor_common import events

from . import logic
from .models import (
    CustomerScore,
    Earning,
    InsuranceClaim,
    InsuranceEnrollment,
    Job,
    ModuleCompletion,
    Payout,
    Provider,
    Review,
    SafetyIncident,
    ShareLink,
    TrainingModule,
)

S = Job.Status
LIVE = (S.ACCEPTED, S.ON_THE_WAY, S.WORKING)


def job_for(user_id, source, source_id):
    job = Job.objects.select_related("provider").filter(source=source, source_id=source_id).first()
    if job is None:
        raise NotFound("Job not found.")
    if job.user_id == int(user_id):
        return job, "customer"
    if job.provider and job.provider.user_id == int(user_id):
        return job, "provider"
    raise PermissionDenied("You are not part of this job.")


# ---- SOS ---------------------------------------------------------------------------------------

@transaction.atomic
def raise_sos(user_id, source, source_id, latitude=None, longitude=None, note=""):
    job, role = job_for(user_id, source, source_id)
    incident = SafetyIncident.objects.create(job=job, raised_by=user_id, role=role, latitude=latitude, longitude=longitude, note=note)
    sms = []
    if role == "provider" and job.provider.emergency_contact_phone:
        sms.append(job.provider.emergency_contact_phone)
    events.publish("safety.sos", {
        "incident_id": incident.id, "role": role, "job_title": job.title, "area_name": job.area_name,
        "address_line": job.address_line, "latitude": str(latitude or job.latitude or ""), "longitude": str(longitude or job.longitude or ""),
        "provider_name": job.provider.full_name if job.provider else "", "customer_name": job.customer_name,
        "sms_phones": sms,
    })
    return incident


def resolve_incident(incident, resolution):
    if not resolution:
        raise ValidationError({"resolution": "Write what was done."})
    incident.status, incident.resolution, incident.resolved_at = SafetyIncident.Status.RESOLVED, resolution, timezone.now()
    incident.save()
    return incident


# ---- live job sharing ---------------------------------------------------------------------------

def create_share(user_id, source, source_id):
    job, role = job_for(user_id, source, source_id)
    if role != "customer":
        raise PermissionDenied("Only the customer can share a job.")
    return ShareLink.objects.create(job=job, token=secrets.token_urlsafe(16)[:22], created_by=user_id,
                                    expires_at=timezone.now() + timedelta(hours=settings.SHARE_LINK_HOURS))


def shared_view(token):
    link = ShareLink.objects.select_related("job__provider").filter(token=token, expires_at__gt=timezone.now()).first()
    if link is None:
        raise NotFound("This link has expired.")
    job, p = link.job, link.job.provider
    live = job.status in (S.ON_THE_WAY, S.WORKING) and p and p.last_latitude is not None
    return {
        "title": job.title, "status": job.status, "scheduled_date": job.scheduled_date, "slot": job.slot,
        "provider_first_name": p.full_name.split(" ")[0] if p else "",
        "provider_verified": bool(p and p.status == Provider.Status.APPROVED),
        "location": {"latitude": str(p.last_latitude), "longitude": str(p.last_longitude), "updated_at": p.location_updated_at} if live else None,
        "expires_at": link.expires_at,
    }


# ---- contact window -----------------------------------------------------------------------------

def contact_visible(job):
    """Phone numbers are for coordinating the visit: shown while the job is live and for 48 hours after it ends."""
    if job.status in LIVE:
        return True
    if job.status == S.COMPLETED and job.completed_at:
        return timezone.now() < job.completed_at + timedelta(hours=settings.CONTACT_VISIBLE_HOURS_AFTER)
    return False


# ---- two-way ratings and disputes ---------------------------------------------------------------

@transaction.atomic
def rate_customer(job, provider, rating, feedback=""):
    if job.provider_id != provider.id or job.status != S.COMPLETED:
        raise ValidationError({"job": "You can rate the customer of a job you completed."})
    if job.customer_rating:
        raise ValidationError({"job": "Already rated."})
    if not 1 <= int(rating) <= 5:
        raise ValidationError({"rating": "Rate from 1 to 5."})
    job.customer_rating, job.customer_feedback = rating, feedback
    job.save(update_fields=["customer_rating", "customer_feedback"])
    score, _ = CustomerScore.objects.get_or_create(user_id=job.user_id)
    CustomerScore.objects.filter(pk=score.pk).update(rating_sum=F("rating_sum") + int(rating), rating_count=F("rating_count") + 1)
    return job


def customer_score(user_id):
    score = CustomerScore.objects.filter(user_id=user_id).first()
    return {"average": score.average, "count": score.rating_count} if score else {"average": None, "count": 0}


def dispute_review(review, provider, reason):
    if review.provider_id != provider.id:
        raise PermissionDenied()
    if review.dispute:
        raise ValidationError({"review": "This review was already disputed."})
    if len(reason.strip()) < 10:
        raise ValidationError({"reason": "Explain what is wrong with the review."})
    review.dispute, review.dispute_reason = Review.Dispute.OPEN, reason.strip()
    review.save(update_fields=["dispute", "dispute_reason"])
    return review


@transaction.atomic
def decide_dispute(review, uphold, note=""):
    if review.dispute != Review.Dispute.OPEN:
        raise ValidationError({"review": "No open dispute."})
    review.dispute = Review.Dispute.UPHELD if uphold else Review.Dispute.REJECTED
    review.hidden, review.dispute_note = bool(uphold), note
    review.save(update_fields=["dispute", "hidden", "dispute_note"])
    logic.recompute_rating(review.provider)
    return review


# ---- insurance ----------------------------------------------------------------------------------

def active_enrollment(provider):
    return provider.insurance.filter(status=InsuranceEnrollment.Status.ACTIVE).select_related("plan").first()


def enroll(provider, plan):
    if not plan.is_active:
        raise ValidationError({"plan": "This plan is not available."})
    if active_enrollment(provider):
        raise ValidationError({"plan": "You already have cover. Cancel it first to switch."})
    return InsuranceEnrollment.objects.create(provider=provider, plan=plan)


def file_claim(provider, description, photo_urls):
    enrollment = active_enrollment(provider)
    if enrollment is None:
        raise ValidationError({"claim": "You are not insured."})
    if not description.strip():
        raise ValidationError({"description": "Describe what happened."})
    return InsuranceClaim.objects.create(enrollment=enrollment, description=description.strip(), photo_urls=photo_urls)


def take_premium(provider, payout_amount):
    """This week's premium, once per ISO week, if the payout can cover it."""
    enrollment = active_enrollment(provider)
    if enrollment is None:
        return Decimal("0")
    year, week, _ = timezone.localdate().isocalendar()
    this_week = f"{year}-W{week:02d}"
    premium = enrollment.plan.weekly_premium
    if enrollment.last_premium_week == this_week or payout_amount <= premium:
        return Decimal("0")
    enrollment.last_premium_week = this_week
    enrollment.save(update_fields=["last_premium_week"])
    return premium


# ---- payouts ------------------------------------------------------------------------------------

@transaction.atomic
def request_payout(provider, instant=False):
    if not provider.payout_method or not provider.payout_account:
        raise ValidationError({"payout": "Add your bKash or Nagad number in your profile first."})
    pending = provider.earnings.select_for_update().filter(status=Earning.Status.PENDING)
    earned = pending.aggregate(s=Sum("net"))["s"] or Decimal("0")
    if earned <= 0:
        raise ValidationError({"payout": "Nothing to pay out yet."})
    fee = Decimal("0")
    if instant:
        fee = max(Decimal(settings.INSTANT_PAYOUT_MIN_FEE),
                  (earned * Decimal(settings.INSTANT_PAYOUT_FEE_PERCENT) / 100).quantize(Decimal("0.01"), ROUND_HALF_UP))
        if earned <= fee:
            raise ValidationError({"payout": "Too little for an instant payout; wait for the weekly payout."})
    premium = take_premium(provider, earned - fee)
    payout = Payout.objects.create(provider=provider, amount=earned - fee - premium, instant=instant, fee=fee,
                                   insurance_premium=premium, method=provider.payout_method, account=provider.payout_account)
    pending.update(status=Earning.Status.IN_PAYOUT, payout=payout)
    if instant and settings.PAYOUT_BACKEND == "mock":
        # Development: pretend the bKash/Nagad disbursement went through.
        logic.mark_payout_paid(payout, f"MOCK-{payout.id:06d}")
    return payout


# ---- training -----------------------------------------------------------------------------------

def modules_for(provider):
    qs = TrainingModule.objects.filter(is_active=True)
    return [m for m in qs if not m.category_slug or m.category_slug in provider.skills]


@transaction.atomic
def submit_quiz(provider, module, answers):
    questions = module.questions
    if not questions or len(answers) != len(questions):
        raise ValidationError({"answers": "Answer every question."})
    correct = sum(1 for q, a in zip(questions, answers) if int(a) == int(q["answer"]))
    score = round(100 * correct / len(questions))
    passed = score >= module.pass_percent
    completion, created = ModuleCompletion.objects.get_or_create(
        provider=provider, module=module, defaults={"score": score, "passed": passed}
    )
    if not created:
        if completion.passed:
            return completion
        completion.score, completion.passed, completion.attempts = score, passed, completion.attempts + 1
    if passed and not completion.certificate_code:
        completion.certificate_code = secrets.token_hex(5).upper()
        badges = set(provider.badges) | {f"trained:{module.slug}"}
        provider.badges = sorted(badges)
        provider.save(update_fields=["badges"])
    completion.save()
    return completion
