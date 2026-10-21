from django.db import models


class Fact(models.Model):
    """One business event, flattened for reporting. Raw payload kept for questions not foreseen here."""

    event = models.CharField(max_length=40, db_index=True)
    user_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    area_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    area_name = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=60, blank=True)
    title = models.CharField(max_length=200, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    ref = models.CharField(max_length=60, blank=True)
    payload = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["event", "occurred_at"])]
