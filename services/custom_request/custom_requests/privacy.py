from shohor_common.privacy import DELETED_NAME, iso

from .models import CustomRequest


def collect(user_id):
    return [
        {"service_type": r.service_type, "description": r.description, "status": r.status, "final_amount": str(r.final_amount or ""),
         "address": f"{r.address_line}, {r.area_name}", "created_at": iso(r.created_at)}
        for r in CustomRequest.objects.filter(user_id=user_id)
    ]


def forget(user_id):
    CustomRequest.objects.filter(user_id=user_id).update(customer_name=DELETED_NAME, customer_phone="", address_line="",
                                                         latitude=None, longitude=None, media_urls=[], description="")
