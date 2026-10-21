from django.db import models


class Notification(models.Model):
    user_id = models.PositiveBigIntegerField(db_index=True)
    kind = models.CharField(max_length=40)
    title_bn = models.CharField(max_length=200)
    title_en = models.CharField(max_length=200)
    body_bn = models.TextField(blank=True)
    body_en = models.TextField(blank=True)
    # Path inside the app the user is in, e.g. /orders/12
    link = models.CharField(max_length=200, blank=True)
    app = models.CharField(max_length=10, default="customer", help_text="customer / provider / admin")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user_id", "read_at"])]


class SmsLog(models.Model):
    phone = models.CharField(max_length=11)
    body = models.TextField()
    status = models.CharField(max_length=10, default="sent")
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class WhatsAppLog(models.Model):
    phone = models.CharField(max_length=15)
    body = models.TextField()
    template = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=10, default="sent")
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Broadcast(models.Model):
    audience = models.CharField(max_length=20)
    title_bn = models.CharField(max_length=200)
    title_en = models.CharField(max_length=200)
    body_bn = models.TextField(blank=True)
    body_en = models.TextField(blank=True)
    link = models.CharField(max_length=200, blank=True)
    sent_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
