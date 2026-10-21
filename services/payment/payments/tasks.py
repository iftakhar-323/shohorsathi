from celery import shared_task

from . import logic


@shared_task(name="payment.order.status_changed")
def order_status_changed(payload):
    logic.on_status("order", payload, done={"completed"}, cancelled={"cancelled"})


@shared_task(name="payment.custom_request.status_changed")
def custom_request_status_changed(payload):
    logic.on_status("custom_request_advance", payload, done={"completed"}, cancelled={"cancelled", "rejected"})


@shared_task(name="payment.subscription.status_changed")
def subscription_status_changed(payload):
    # Cancelled subscriptions keep their unused value as credit for the customer (see the subscription service).
    logic.on_status("subscription", payload, done={"expired"}, cancelled=set())
