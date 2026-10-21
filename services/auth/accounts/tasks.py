from celery import shared_task
from shohor_common import roles

from .models import User


@shared_task(name="auth.provider.approved")
def provider_approved(payload):
    User.objects.filter(pk=payload["user_id"], role=roles.CUSTOMER).update(role=roles.PROVIDER)


@shared_task(name="auth.provider.suspended")
def provider_suspended(payload):
    User.objects.filter(pk=payload["user_id"], role=roles.PROVIDER).update(role=roles.CUSTOMER)
