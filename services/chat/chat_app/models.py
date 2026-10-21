from django.db import models


class Conversation(models.Model):
    class Kind(models.TextChoices):
        JOB = "job", "Customer ↔ provider about a job"
        SUPPORT = "support", "Customer ↔ ShohorSathi support"

    kind = models.CharField(max_length=8, choices=Kind.choices)
    source = models.CharField(max_length=20, blank=True)
    source_id = models.PositiveBigIntegerField(null=True, blank=True)
    title = models.CharField(max_length=200)
    customer_user_id = models.PositiveBigIntegerField(db_index=True)
    customer_name = models.CharField(max_length=120, blank=True)
    provider_user_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    provider_name = models.CharField(max_length=120, blank=True)
    is_open = models.BooleanField(default=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_message_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["kind", "source", "source_id"], condition=models.Q(kind="job"), name="one_chat_per_job"),
        ]

    def participant_ids(self):
        return {i for i in (self.customer_user_id, self.provider_user_id) if i}


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender_user_id = models.PositiveBigIntegerField(null=True, blank=True)
    sender_role = models.CharField(max_length=10, help_text="customer / provider / admin / bot")
    sender_name = models.CharField(max_length=120, blank=True)
    body = models.TextField(max_length=4000)
    attachment_url = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class ReadState(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="reads")
    user_id = models.PositiveBigIntegerField()
    last_read_id = models.PositiveBigIntegerField(default=0)

    class Meta:
        unique_together = [("conversation", "user_id")]
