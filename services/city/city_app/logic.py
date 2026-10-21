import math
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from shohor_common import events

from .models import Comment, Issue, IssueUpdate, IssueUpvote, Post, PostLike

I = Issue.Status
# status -> statuses an admin may move to
FLOW = {
    I.REPORTED: {I.FORWARDED, I.IN_PROGRESS, I.RESOLVED, I.REJECTED},
    I.FORWARDED: {I.IN_PROGRESS, I.RESOLVED, I.REJECTED},
    I.IN_PROGRESS: {I.RESOLVED},
    I.RESOLVED: set(),
    I.REJECTED: {I.REPORTED},
}
DUPLICATE_RADIUS_M = 50


class DuplicateIssue(Exception):
    def __init__(self, issue):
        self.issue = issue


def km_between(lat1, lng1, lat2, lng2):
    """Haversine distance in km. (PostGIS can replace this once areas grow large.)"""
    lat1, lng1, lat2, lng2 = map(lambda v: math.radians(float(v)), (lat1, lng1, lat2, lng2))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def near(qs, lat, lng, radius_km):
    """Bounding box in SQL (uses the lat/lng index), then exact distance in Python."""
    dlat = Decimal(radius_km / 111)
    dlng = Decimal(radius_km / (111 * max(math.cos(math.radians(float(lat))), 0.01)))
    lat, lng = Decimal(str(lat)), Decimal(str(lng))
    box = qs.filter(latitude__range=(lat - dlat, lat + dlat), longitude__range=(lng - dlng, lng + dlng))
    rows = []
    for issue in box:
        d = km_between(lat, lng, issue.latitude, issue.longitude)
        if d <= radius_km:
            issue.distance_km = round(d, 2)
            rows.append(issue)
    return sorted(rows, key=lambda i: i.distance_km)


def similar_open(category, lat, lng):
    """An open issue of the same kind within ~50 m: suggest upvoting it instead of a duplicate."""
    open_issues = Issue.objects.filter(category=category).exclude(status__in=[I.RESOLVED, I.REJECTED])
    found = near(open_issues, lat, lng, DUPLICATE_RADIUS_M / 1000)
    return found[0] if found else None


@transaction.atomic
def report(user_id, name, data, force=False):
    if not data.get("photo_urls"):
        raise ValidationError({"photo_urls": "Add at least one photo."})
    if not force and (dup := similar_open(data["category"], data["latitude"], data["longitude"])):
        raise DuplicateIssue(dup)
    issue = Issue.objects.create(user_id=user_id, reporter_name=name, **data)
    IssueUpdate.objects.create(issue=issue, status=I.REPORTED)
    IssueUpvote.objects.create(issue=issue, user_id=user_id)
    Issue.objects.filter(pk=issue.pk).update(upvote_count=1)
    issue.upvote_count = 1
    return issue


@transaction.atomic
def toggle_upvote(issue, user_id):
    try:
        with transaction.atomic():
            IssueUpvote.objects.create(issue=issue, user_id=user_id)
        delta = 1
    except IntegrityError:
        IssueUpvote.objects.filter(issue=issue, user_id=user_id).delete()
        delta = -1
    Issue.objects.filter(pk=issue.pk).update(upvote_count=F("upvote_count") + delta)
    issue.refresh_from_db(fields=["upvote_count"])
    return delta > 0


@transaction.atomic
def change_status(issue, status, note="", authority=None, photos=None):
    if status not in FLOW.get(issue.status, set()):
        raise ValidationError({"status": f"Cannot move from {issue.status} to {status}."})
    if status == I.FORWARDED and authority is None:
        raise ValidationError({"authority": "Pick who it is forwarded to."})
    if status == I.REJECTED and not note:
        raise ValidationError({"note": "Tell the reporter why."})
    issue.status = status
    if authority is not None:
        issue.authority = authority
    if note:
        issue.admin_note = note
    if status == I.RESOLVED:
        issue.resolved_at = timezone.now()
        issue.resolved_photo_urls = photos or []
    issue.save()
    who = f" → {authority.name_bn}" if authority else ""
    IssueUpdate.objects.create(issue=issue, status=status, note=(note + who).strip())
    # Everyone who reported or upvoted hears about it.
    for uid in set(issue.upvotes.values_list("user_id", flat=True)) | {issue.user_id}:
        events.publish("issue.status_changed", {"issue_id": issue.id, "user_id": uid, "status": status, "title": issue.title})
    return issue


@transaction.atomic
def toggle_like(post, user_id):
    try:
        with transaction.atomic():
            PostLike.objects.create(post=post, user_id=user_id)
        delta = 1
    except IntegrityError:
        PostLike.objects.filter(post=post, user_id=user_id).delete()
        delta = -1
    Post.objects.filter(pk=post.pk).update(like_count=F("like_count") + delta)
    post.refresh_from_db(fields=["like_count"])
    return delta > 0


@transaction.atomic
def add_comment(post, user_id, name, body):
    if not body.strip():
        raise ValidationError({"body": "Write something."})
    comment = Comment.objects.create(post=post, user_id=user_id, author_name=name, body=body.strip())
    Post.objects.filter(pk=post.pk).update(comment_count=F("comment_count") + 1)
    return comment
