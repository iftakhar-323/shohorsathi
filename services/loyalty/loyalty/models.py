import secrets

from django.db import models


def new_code():
    return secrets.token_hex(3).upper()


class Account(models.Model):
    user_id = models.PositiveBigIntegerField(unique=True)
    points = models.PositiveIntegerField(default=0)
    # ShohorSathi Credit: closed-loop store credit from refunds, referrals and promotions. It can only be spent on
    # ShohorSathi; it cannot be topped up with money, withdrawn or transferred. This keeps it apart from e-money
    # (which needs a Bangladesh Bank PSP licence); confirm the classification with counsel before launch.
    wallet = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    referral_code = models.CharField(max_length=8, unique=True, default=new_code)
    referred_by = models.PositiveBigIntegerField(null=True, blank=True)
    completed_orders = models.PositiveIntegerField(default=0)
    renewals = models.PositiveIntegerField(default=0)
    referrals = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def badges(self):
        earned = []
        if self.completed_orders >= 1:
            earned.append("first_order")
        if self.completed_orders >= 5:
            earned.append("regular")
        if self.renewals >= 1:
            earned.append("loyal_subscriber")
        if self.referrals >= 1:
            earned.append("referrer")
        if self.points >= 500:
            earned.append("gold")
        return earned


class Entry(models.Model):
    """One movement of points or wallet money. (user, kind, reason, ref) is unique, so replayed events are ignored."""

    class Kind(models.TextChoices):
        POINTS = "points"
        WALLET = "wallet"

    user_id = models.PositiveBigIntegerField(db_index=True)
    kind = models.CharField(max_length=6, choices=Kind.choices)
    delta = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=40)
    ref = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("user_id", "kind", "reason", "ref")]


class Redemption(models.Model):
    """Points used as a discount and/or wallet money used to pay, per order; reversed if the order is cancelled."""

    user_id = models.PositiveBigIntegerField()
    order_id = models.PositiveBigIntegerField(unique=True)
    points = models.PositiveIntegerField(default=0)
    wallet_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reversed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

