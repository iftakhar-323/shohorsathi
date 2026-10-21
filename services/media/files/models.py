import uuid

from django.db import models


def upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"{instance.visibility}/{instance.purpose}/{instance.created_day:%Y/%m}/{uuid.uuid4().hex}.{ext}"


class MediaFile(models.Model):
    class Visibility(models.TextChoices):
        PUBLIC = "public"
        PRIVATE = "private"

    class Purpose(models.TextChoices):
        PROBLEM_PHOTO = "problem_photo"
        JOB_PHOTO = "job_photo"
        PROFILE_PHOTO = "profile_photo"
        NID = "nid"
        KITCHEN = "kitchen"
        ISSUE_PHOTO = "issue_photo"
        CATALOG = "catalog"
        CHAT = "chat"
        OTHER = "other"

    owner_user_id = models.PositiveBigIntegerField(db_index=True)
    file = models.FileField(upload_to=upload_path)
    visibility = models.CharField(max_length=8, choices=Visibility.choices)
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.OTHER)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveIntegerField()
    # Private files (NID, ID cards) are stored encrypted; see files/crypto.py.
    encrypted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def created_day(self):
        from django.utils import timezone

        return self.created_at or timezone.now()


class MediaAccess(models.Model):
    """Who opened a private file, and when (access log for identity documents)."""

    media = models.ForeignKey(MediaFile, on_delete=models.CASCADE, related_name="accesses")
    user_id = models.PositiveBigIntegerField()
    role = models.CharField(max_length=10)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
