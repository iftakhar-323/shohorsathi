"""Data protection duties: purge identity documents we may no longer keep, export, and account deletion."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from shohor_common import internal
from shohor_common.privacy import DELETED_NAME, iso

from .models import Job, Provider, Review

DOCUMENT_FIELDS = ("photo_url", "nid_front_url", "nid_back_url")


def purge_documents(provider):
    urls = [getattr(provider, f) for f in DOCUMENT_FIELDS if getattr(provider, f)] + list(provider.kitchen_photo_urls)
    if urls:
        internal.post("media", "/api/internal/media/delete/", {"urls": urls})
    for f in DOCUMENT_FIELDS:
        setattr(provider, f, "")
    provider.kitchen_photo_urls = []
    provider.nid_number = ""
    provider.save()


def purge_rejected():
    """Rejected applicants' NID and photos are deleted after the retention period (default 90 days)."""
    cutoff = timezone.now() - timedelta(days=settings.REJECTED_DOCUMENT_RETENTION_DAYS)
    n = 0
    for provider in Provider.objects.filter(status=Provider.Status.REJECTED, reviewed_at__lt=cutoff).exclude(nid_front_url="", nid_number=""):
        purge_documents(provider)
        n += 1
    return n


def collect(user_id):
    p = Provider.objects.filter(user_id=user_id).first()
    profile = None
    if p:
        profile = {"type": p.provider_type, "status": p.status, "skills": p.skills, "areas": p.area_ids, "bio": p.bio,
                   "nid_number": p.nid_number, "payout": f"{p.payout_method} {p.payout_account}".strip(), "rating": str(p.rating_avg),
                   "jobs_completed": p.jobs_completed, "joined": iso(p.created_at)}
    return {
        "provider_profile": profile,
        "reviews_written": [{"job": r.job.title, "rating": r.rating, "comment": r.comment, "at": iso(r.created_at)}
                            for r in Review.objects.filter(user_id=user_id).select_related("job")],
    }


@transaction.atomic
def forget(user_id):
    # As a customer: the job keeps its history, not the person's contact details.
    Job.objects.filter(user_id=user_id).update(customer_name=DELETED_NAME, customer_phone="", address_line="", latitude=None,
                                               longitude=None, description="", photo_urls=[])
    Review.objects.filter(user_id=user_id).update(comment="")
    # As a provider: documents go, the profile stops taking work.
    provider = Provider.objects.filter(user_id=user_id).first()
    if provider:
        purge_documents(provider)
        provider.full_name, provider.phone, provider.bio, provider.payout_account = DELETED_NAME, "", "", ""
        provider.status, provider.is_online = Provider.Status.SUSPENDED, False
        provider.last_latitude = provider.last_longitude = None
        provider.save()
