from .models import Membership


def collect(user_id):
    return [{"organization": m.organization.name, "role": m.role} for m in Membership.objects.filter(user_id=user_id).select_related("organization")]


def forget(user_id):
    Membership.objects.filter(user_id=user_id).delete()
