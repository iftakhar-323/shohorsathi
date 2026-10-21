from django.contrib.postgres.fields import ArrayField
from django.db import models


class Authority(models.Model):
    """Who an issue is forwarded to: a city corporation ward office, WASA zone, DESCO/DPDC, etc."""

    name_bn = models.CharField(max_length=160)
    name_en = models.CharField(max_length=160)
    contact_phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    categories = ArrayField(models.CharField(max_length=20), default=list, blank=True, help_text="Issue categories it handles")
    area_ids = ArrayField(models.PositiveIntegerField(), default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "authorities"

    def __str__(self):
        return self.name_en


class Issue(models.Model):
    class Category(models.TextChoices):
        GARBAGE = "garbage"
        STREETLIGHT = "streetlight"
        WATERLOGGING = "waterlogging"
        ROAD_DAMAGE = "road_damage"
        DRAINAGE = "drainage"
        MOSQUITO = "mosquito"
        WATER_SUPPLY = "water_supply"
        OTHER = "other"

    class Status(models.TextChoices):
        REPORTED = "reported"
        FORWARDED = "forwarded"
        IN_PROGRESS = "in_progress"
        RESOLVED = "resolved"
        REJECTED = "rejected"

    user_id = models.PositiveBigIntegerField(db_index=True)
    reporter_name = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    photo_urls = models.JSONField(default=list)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    landmark = models.CharField(max_length=200, blank=True)
    area_id = models.PositiveIntegerField(db_index=True)
    area_name = models.CharField(max_length=120)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REPORTED)
    authority = models.ForeignKey(Authority, null=True, blank=True, on_delete=models.SET_NULL, related_name="issues")
    admin_note = models.TextField(blank=True)
    resolved_photo_urls = models.JSONField(default=list, blank=True)
    upvote_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["latitude", "longitude"]), models.Index(fields=["status", "category"])]


class IssueUpvote(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="upvotes")
    user_id = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("issue", "user_id")]


class IssueUpdate(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="updates")
    status = models.CharField(max_length=12)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Post(models.Model):
    class Kind(models.TextChoices):
        TIP = "tip"
        RECOMMENDATION = "recommendation", "Recommend a provider"
        QUESTION = "question"
        ALERT = "alert", "Neighbourhood alert"

    user_id = models.PositiveBigIntegerField()
    author_name = models.CharField(max_length=120)
    area_id = models.PositiveIntegerField(db_index=True)
    area_name = models.CharField(max_length=120)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    body = models.TextField(max_length=3000)
    photo_urls = models.JSONField(default=list, blank=True)
    # For recommendations: the provider's public profile id
    provider_id = models.PositiveBigIntegerField(null=True, blank=True)
    provider_name = models.CharField(max_length=120, blank=True)
    like_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user_id = models.PositiveBigIntegerField()

    class Meta:
        unique_together = [("post", "user_id")]


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    user_id = models.PositiveBigIntegerField()
    author_name = models.CharField(max_length=120)
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
