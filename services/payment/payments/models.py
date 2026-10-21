import secrets

from django.db import models


def new_tran_id():
    return "SS" + secrets.token_hex(8).upper()


class Payment(models.Model):
    class Purpose(models.TextChoices):
        ORDER = "order"
        SUBSCRIPTION = "subscription"
        CUSTOM_REQUEST_ADVANCE = "custom_request_advance"

    class Status(models.TextChoices):
        INITIATED = "initiated"
        HELD = "held", "Paid, held in escrow"
        RELEASED = "released"
        FAILED = "failed"
        CANCELLED = "cancelled"
        REFUNDED = "refunded"

    user_id = models.PositiveBigIntegerField(db_index=True)
    purpose = models.CharField(max_length=24, choices=Purpose.choices)
    reference_id = models.PositiveBigIntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="BDT")
    gateway = models.CharField(max_length=16)
    tran_id = models.CharField(max_length=32, unique=True, default=new_tran_id)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.INITIATED)
    method = models.CharField(max_length=40, blank=True, help_text="bKash / Nagad / card, as reported by the gateway")
    val_id = models.CharField(max_length=64, blank=True)
    bank_tran_id = models.CharField(max_length=64, blank=True)
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gateway_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["purpose", "reference_id"])]


class LedgerEntry(models.Model):
    """Double entry: every movement debits one account and credits another by the same amount."""

    class Account(models.TextChoices):
        GATEWAY = "gateway", "Gateway clearing"
        ESCROW = "escrow", "Held for customers"
        SETTLED = "settled", "Released to platform/providers"
        REFUNDS = "refunds", "Refunded to customers"

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="ledger")
    debit = models.CharField(max_length=10, choices=Account.choices)
    credit = models.CharField(max_length=10, choices=Account.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    memo = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class RefundRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested"
        REFUNDED = "refunded"
        REJECTED = "rejected"
        FAILED = "failed"

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    user_id = models.PositiveBigIntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REQUESTED)
    automatic = models.BooleanField(default=False)
    admin_note = models.CharField(max_length=255, blank=True)
    gateway_ref = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
