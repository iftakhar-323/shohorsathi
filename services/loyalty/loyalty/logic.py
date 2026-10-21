from decimal import ROUND_DOWN, Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError
from shohor_common import events

from .models import Account, Entry, Redemption, TopUp

K = Entry.Kind


def account(user_id):
    acc, _ = Account.objects.get_or_create(user_id=user_id)
    return acc


def locked(user_id):
    account(user_id)
    return Account.objects.select_for_update().get(user_id=user_id)


@transaction.atomic
def move(user_id, kind, delta, reason, ref=""):
    """Apply one ledger entry once. Returns False if this (reason, ref) was already applied."""
    try:
        with transaction.atomic():
            Entry.objects.create(user_id=user_id, kind=kind, delta=delta, reason=reason, ref=str(ref))
    except IntegrityError:
        return False
    acc = locked(user_id)
    if kind == K.POINTS:
        if acc.points + int(delta) < 0:
            raise ValidationError({"points": "Not enough points."})
        acc.points += int(delta)
    else:
        if acc.wallet + Decimal(delta) < 0:
            raise ValidationError({"wallet": "Not enough wallet balance."})
        acc.wallet += Decimal(delta)
    acc.save(update_fields=["points", "wallet"])
    if kind == K.POINTS and delta > 0:
        events.publish("loyalty.points_earned", {"user_id": user_id, "points": int(delta), "reason": reason, "total": acc.points})
    return True


# ---- earning ----------------------------------------------------------------------------------

@transaction.atomic
def order_completed(payload):
    user_id = payload["user_id"]
    points = int(Decimal(payload.get("total", "0")) / 100 * Decimal(settings.POINTS_PER_100_TAKA))
    if not move(user_id, K.POINTS, points, "order", payload["order_id"]) and points:
        return  # replayed event
    acc = locked(user_id)
    acc.completed_orders += 1
    acc.save(update_fields=["completed_orders"])
    if acc.completed_orders == 1 and acc.referred_by:
        # The referral pays out once the new customer actually completes an order.
        move(acc.referred_by, K.WALLET, Decimal(settings.REFERRAL_BONUS_TAKA), "referral", user_id)
        move(user_id, K.WALLET, Decimal(settings.REFERRAL_WELCOME_TAKA), "referral_welcome", user_id)
        referrer = locked(acc.referred_by)
        referrer.referrals += 1
        referrer.save(update_fields=["referrals"])


def subscription_bonus(payload, renewal):
    move(payload["user_id"], K.POINTS, settings.SUBSCRIPTION_BONUS_POINTS, "subscription_renewal" if renewal else "subscription", payload["subscription_id"])
    if renewal:
        acc = locked(payload["user_id"])
        acc.renewals += 1
        acc.save(update_fields=["renewals"])


@transaction.atomic
def apply_referral(user_id, code):
    acc = locked(user_id)
    if acc.referred_by:
        raise ValidationError({"code": "A referral code was already used."})
    if acc.completed_orders:
        raise ValidationError({"code": "Referral codes are for new customers."})
    referrer = Account.objects.filter(referral_code=code.strip().upper()).first()
    if referrer is None or referrer.user_id == user_id:
        raise ValidationError({"code": "Invalid code."})
    acc.referred_by = referrer.user_id
    acc.save(update_fields=["referred_by"])
    return acc


# ---- spending (called by the order service during checkout) --------------------------------

@transaction.atomic
def redeem_points(user_id, order_id, points, subtotal):
    acc = locked(user_id)
    cap = int((Decimal(subtotal) * Decimal(settings.MAX_REDEEM_PERCENT) / 100 / Decimal(settings.POINT_VALUE_TAKA)).to_integral_value(ROUND_DOWN))
    points = min(int(points), acc.points, cap)
    if points <= 0:
        return Decimal("0")
    move(user_id, K.POINTS, -points, "redeem", order_id)
    red, _ = Redemption.objects.get_or_create(order_id=order_id, defaults={"user_id": user_id})
    red.points = points
    red.save(update_fields=["points"])
    return Decimal(points) * Decimal(settings.POINT_VALUE_TAKA)


@transaction.atomic
def wallet_pay(user_id, order_id, amount):
    amount = Decimal(amount)
    if account(user_id).wallet < amount:
        raise ValidationError({"wallet": "Not enough wallet balance."})
    move(user_id, K.WALLET, -amount, "pay_order", order_id)
    red, _ = Redemption.objects.get_or_create(order_id=order_id, defaults={"user_id": user_id})
    red.wallet_paid = amount
    red.save(update_fields=["wallet_paid"])


@transaction.atomic
def order_cancelled(payload):
    red = Redemption.objects.select_for_update().filter(order_id=payload["order_id"], reversed=False).first()
    if red is None:
        return
    if red.points:
        move(red.user_id, K.POINTS, red.points, "redeem_reversed", red.order_id)
    if red.wallet_paid:
        move(red.user_id, K.WALLET, red.wallet_paid, "pay_order_reversed", red.order_id)
    red.reversed = True
    red.save(update_fields=["reversed"])


def topup_paid(payload):
    if payload.get("purpose") != "wallet_topup":
        return
    with transaction.atomic():
        topup = TopUp.objects.select_for_update().filter(pk=payload["reference_id"], paid=False).first()
        if topup is None:
            return
        topup.paid = True
        topup.save(update_fields=["paid"])
        move(topup.user_id, K.WALLET, topup.amount, "topup", topup.id)
