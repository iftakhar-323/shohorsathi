from django.db import models


class OutboxEvent(models.Model):
    """An event written in the same transaction as the change that caused it, then relayed to the broker.

    If the broker is down when the transaction commits, the row stays unsent and the relay task retries it,
    so no event is lost (transactional outbox).
    """

    event = models.CharField(max_length=60)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["id"]
