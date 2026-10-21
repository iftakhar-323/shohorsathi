from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from shohor_common import events, internal

from .gateways import GatewayError, gateway, get_gateway
from .models import LedgerEntry, Payment, PaymentAgreement, RefundRequest

P = Payment.Status
A = LedgerEntry.Account

# Where to ask "how much does this cost, and may this user pay it?"
PAYABLE = {
    Payment.Purpose.ORDER: ("order", "/api/internal/orders/{id}/payable/"),
    Payment.Purpose.SUBSCRIPTION: ("subscription", "/api/internal/subscriptions/{id}/payable/"),
    Payment.Purpose.CUSTOM_REQUEST_ADVANCE: ("custom_request", "/api/internal/custom-requests/{id}/payable/"),
}


def post(payment, debit, credit, amount, memo):
    LedgerEntry.objects.create(payment=payment, debit=debit, credit=credit, amount=amount, memo=memo)


@transaction.atomic
def initiate(user, purpose, reference_id, gateway_name=None):
    service, path = PAYABLE[purpose]
    info = internal.get(service, path.format(id=reference_id))
    if info is None:
        raise ValidationError({"reference_id": "Not found."})
    if int(info["user_id"]) != int(user["id"]):
        raise PermissionDenied("This is not yours to pay.")
    if not info["payable"] or Decimal(info["amount"]) <= 0:
        raise ValidationError({"reference_id": "Nothing to pay for this."})
    if Payment.objects.filter(purpose=purpose, reference_id=reference_id, status__in=[P.HELD, P.RELEASED]).exists():
        raise ValidationError({"reference_id": "Already paid."})
    gw = get_gateway(gateway_name)
    payment = Payment.objects.create(user_id=user["id"], purpose=purpose, reference_id=reference_id, amount=Decimal(info["amount"]), gateway=gw.name)
    try:
        url = gw.start(payment, user)
    except GatewayError as e:
        payment.status = P.FAILED
        payment.gateway_response = {"error": str(e)}
        payment.save()
        raise ValidationError({"gateway": str(e)})
    return payment, url


@transaction.atomic
def confirm(data):
    """Gateway callback/IPN. Idempotent: replays of the same transaction are ignored."""
    payment = Payment.objects.select_for_update().filter(tran_id=data.get("tran_id", "")).first()
    if payment is None:
        return None
    if payment.status != P.INITIATED:
        return payment
    gw = get_gateway(payment.gateway)
    result = gw.validate(data)
    if not result.get("ok") or result.get("amount") != payment.amount:
        payment.status = P.FAILED
        payment.gateway_response = {k: str(v) for k, v in result.items()}
        payment.save()
        events.publish("payment.failed", {"payment_id": payment.id, "user_id": payment.user_id, "purpose": payment.purpose, "reference_id": payment.reference_id})
        return payment
    payment.status = P.HELD
    payment.val_id, payment.bank_tran_id, payment.method = result["val_id"], result["bank_tran_id"], result.get("method", "")
    payment.paid_at = timezone.now()
    payment.gateway_response = {k: str(v) for k, v in result.items() if k != "raw"}
    payment.save()
    post(payment, A.GATEWAY, A.ESCROW, payment.amount, "Customer paid; held until the work is confirmed")
    events.publish(
        "payment.succeeded",
        {"payment_id": payment.id, "user_id": payment.user_id, "purpose": payment.purpose, "reference_id": payment.reference_id, "amount": str(payment.amount)},
    )
    return payment


def mark_unpaid(tran_id, status):
    Payment.objects.filter(tran_id=tran_id, status=P.INITIATED).update(status=status)


def held_for(purpose, reference_id):
    return Payment.objects.select_for_update().filter(purpose=purpose, reference_id=reference_id, status=P.HELD)


@transaction.atomic
def release(purpose, reference_id):
    for payment in held_for(purpose, reference_id):
        remaining = payment.amount - payment.refunded_amount
        payment.status, payment.released_at = P.RELEASED, timezone.now()
        payment.save(update_fields=["status", "released_at"])
        if remaining > 0:
            post(payment, A.ESCROW, A.SETTLED, remaining, "Work confirmed; released")


def refundable(payment):
    return payment.amount - payment.refunded_amount


@transaction.atomic
def refund(request_row, note="", automatic=False):
    payment = Payment.objects.select_for_update().get(pk=request_row.payment_id)
    if payment.status not in (P.HELD, P.RELEASED):
        raise ValidationError({"payment": "Only a paid payment can be refunded."})
    amount = min(request_row.amount, refundable(payment))
    if amount <= 0:
        raise ValidationError({"amount": "Nothing left to refund."})
    try:
        ref = gateway().refund(payment, amount, request_row.reason)
    except GatewayError as e:
        request_row.status, request_row.admin_note = RefundRequest.Status.FAILED, str(e)
        request_row.save()
        return request_row
    source = A.ESCROW if payment.status == P.HELD else A.SETTLED
    post(payment, source, A.REFUNDS, amount, "Refund: " + request_row.reason[:100])
    payment.refunded_amount += amount
    if payment.refunded_amount >= payment.amount:
        payment.status = P.REFUNDED
    payment.save(update_fields=["refunded_amount", "status"])
    request_row.amount, request_row.status, request_row.gateway_ref = amount, RefundRequest.Status.REFUNDED, ref
    request_row.admin_note = note or request_row.admin_note
    request_row.save()
    events.publish(
        "payment.refunded",
        {"payment_id": payment.id, "user_id": payment.user_id, "purpose": payment.purpose, "reference_id": payment.reference_id,
         "amount": str(amount), "full": payment.status == P.REFUNDED, "automatic": automatic},
    )
    return request_row


def auto_refund(purpose, reference_id, reason):
    with transaction.atomic():
        payments = list(held_for(purpose, reference_id))
    for payment in payments:
        row = RefundRequest.objects.create(payment=payment, user_id=payment.user_id, amount=refundable(payment), reason=reason, automatic=True)
        refund(row, automatic=True)


def on_status(purpose, payload, done, cancelled):
    ref = payload.get("order_id") or payload.get("request_id") or payload.get("subscription_id")
    if payload["status"] in done:
        release(purpose, ref)
    elif payload["status"] in cancelled:
        auto_refund(purpose, ref, f"{purpose} {payload['status']}")


def balances():
    def total(**f):
        return LedgerEntry.objects.filter(**f).aggregate(s=Sum("amount"))["s"] or Decimal("0")

    return {str(acc): f"{total(credit=acc) - total(debit=acc):.2f}" for acc in (A.ESCROW, A.SETTLED, A.REFUNDS)}


# ---- Tokenized Agreements (bKash Auto-Debit) ------------------------------------------------

def create_agreement(user):
    gw = get_gateway("bkash")
    return gw.start_agreement(user)


@transaction.atomic
def execute_agreement(user, agreement_id, payer_reference=""):
    gw = get_gateway("bkash")
    res = gw.execute_agreement(agreement_id, payer_reference)
    agreement, _ = PaymentAgreement.objects.update_or_create(
        agreement_id=agreement_id,
        defaults={
            "user_id": user["id"],
            "gateway": "bkash",
            "payer_reference": payer_reference or str(user.get("phone", "")),
            "status": PaymentAgreement.Status.ACTIVE,
        },
    )
    events.publish("payment.agreement_created", {"user_id": user["id"], "agreement_id": agreement_id, "gateway": "bkash"})
    return agreement


@transaction.atomic
def cancel_agreement(user_id, agreement_id_or_id):
    qs = PaymentAgreement.objects.filter(user_id=user_id)
    if str(agreement_id_or_id).isdigit():
        agreement = qs.filter(id=int(agreement_id_or_id)).first()
    else:
        agreement = qs.filter(agreement_id=agreement_id_or_id).first()
    if not agreement:
        raise ValidationError({"agreement": "Agreement not found."})
    agreement.status = PaymentAgreement.Status.CANCELLED
    agreement.cancelled_at = timezone.now()
    agreement.save(update_fields=["status", "cancelled_at"])
    events.publish("payment.agreement_cancelled", {"user_id": user_id, "agreement_id": agreement.agreement_id})
    return agreement


@transaction.atomic
def charge_agreement(agreement_id, purpose, reference_id, amount=None):
    agreement = PaymentAgreement.objects.filter(agreement_id=agreement_id, status=PaymentAgreement.Status.ACTIVE).first()
    if not agreement:
        raise ValidationError({"agreement": "Active agreement not found."})
    service, path = PAYABLE[purpose]
    info = internal.get(service, path.format(id=reference_id))
    if info is None:
        raise ValidationError({"reference_id": "Not found."})
    if not info["payable"] or Decimal(info["amount"]) <= 0:
        raise ValidationError({"reference_id": "Nothing to pay."})
    charge_amt = Decimal(amount) if amount is not None else Decimal(info["amount"])
    if Payment.objects.filter(purpose=purpose, reference_id=reference_id, status__in=[P.HELD, P.RELEASED]).exists():
        raise ValidationError({"reference_id": "Already paid."})
    gw = get_gateway(agreement.gateway)
    payment = Payment.objects.create(
        user_id=agreement.user_id,
        purpose=purpose,
        reference_id=reference_id,
        amount=charge_amt,
        gateway=gw.name,
        agreement=agreement,
        method="bKash Auto-Debit",
    )
    res = gw.charge_agreement(agreement_id, charge_amt, payment.tran_id)
    if not res.get("ok"):
        payment.status = P.FAILED
        payment.save()
        events.publish("payment.failed", {"payment_id": payment.id, "user_id": payment.user_id, "purpose": payment.purpose, "reference_id": payment.reference_id})
        raise ValidationError({"charge": "bKash auto-debit charge failed."})
    payment.status = P.HELD
    payment.val_id = res["val_id"]
    payment.bank_tran_id = res["bank_tran_id"]
    payment.paid_at = timezone.now()
    payment.save()
    post(payment, A.GATEWAY, A.ESCROW, payment.amount, f"Recurring auto-debit ({agreement.gateway}) held in escrow")
    events.publish(
        "payment.succeeded",
        {"payment_id": payment.id, "user_id": payment.user_id, "purpose": payment.purpose, "reference_id": payment.reference_id, "amount": str(payment.amount)},
    )
    return payment

