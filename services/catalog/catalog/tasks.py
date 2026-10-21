from celery import shared_task
from django.db.models import F
from django.db.models.functions import Greatest

from .models import Product


@shared_task(name="catalog.order.placed")
def order_placed(payload):
    for item in payload["items"]:
        Product.objects.filter(slug=item["slug"]).update(stock=Greatest(F("stock") - item["quantity"], 0))
