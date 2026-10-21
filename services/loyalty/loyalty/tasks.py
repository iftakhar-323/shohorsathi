from celery import shared_task

from . import logic


@shared_task(name="loyalty.order.status_changed")
def order_status_changed(payload):
    if payload["status"] == "completed":
        logic.order_completed(payload)
    elif payload["status"] == "cancelled":
        logic.order_cancelled(payload)


@shared_task(name="loyalty.subscription.created")
def subscription_created(payload):
    if not payload.get("renewal"):
        logic.subscription_bonus(payload, renewal=False)


@shared_task(name="loyalty.subscription.renewed")
def subscription_renewed(payload):
    logic.subscription_bonus({**payload, "subscription_id": payload["subscription_id"]}, renewal=True)


@shared_task(name="loyalty.payment.succeeded")
def payment_succeeded(payload):
    logic.topup_paid(payload)


@shared_task(name="loyalty.order.placed")
def order_placed(payload):
    logic.account(payload["user_id"])  # make sure every customer has an account (and a referral code)
