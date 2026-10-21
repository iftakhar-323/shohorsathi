from django.db import transaction
from django.db.models import F
from shohor_common.privacy import iso

from .models import Comment, Issue, Post


def collect(user_id):
    return {
        "issues": [{"title": i.title, "category": i.category, "status": i.status, "at": iso(i.created_at)} for i in Issue.objects.filter(user_id=user_id)],
        "posts": [{"kind": p.kind, "body": p.body, "at": iso(p.created_at)} for p in Post.objects.filter(user_id=user_id)],
        "comments": [{"body": c.body, "at": iso(c.created_at)} for c in Comment.objects.filter(user_id=user_id)],
    }


@transaction.atomic
def forget(user_id):
    """Civic reports stay (they matter to the neighbourhood) without the reporter's name; own posts are removed."""
    Issue.objects.filter(user_id=user_id).update(reporter_name="")
    for c in Comment.objects.filter(user_id=user_id):
        Post.objects.filter(pk=c.post_id, comment_count__gt=0).update(comment_count=F("comment_count") - 1)
        c.delete()
    Post.objects.filter(user_id=user_id).delete()
