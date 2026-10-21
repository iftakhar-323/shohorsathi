from rest_framework import serializers

from .models import Earning, Job, JobLog, Payout, Provider, Review


class ProviderSerializer(serializers.ModelSerializer):
    trust_score = serializers.IntegerField(read_only=True)

    class Meta:
        model = Provider
        fields = [
            "id", "user_id", "full_name", "phone", "gender", "provider_type", "skills", "area_ids", "bio",
            "experience_years", "nid_number", "photo_url", "nid_front_url", "nid_back_url", "kitchen_photo_urls",
            "status", "rejection_reason", "is_online", "working_days", "work_start", "work_end", "payout_method",
            "payout_account", "rating_avg", "rating_count", "jobs_completed", "badges", "trust_score", "created_at",
            "approved_at",
        ]
        read_only_fields = [
            "id", "user_id", "full_name", "phone", "status", "rejection_reason", "rating_avg", "rating_count",
            "jobs_completed", "badges", "created_at", "approved_at",
        ]

    def validate(self, attrs):
        ptype = attrs.get("provider_type", getattr(self.instance, "provider_type", None))
        kitchen = attrs.get("kitchen_photo_urls", getattr(self.instance, "kitchen_photo_urls", []))
        if ptype == Provider.Type.HOME_CHEF and not kitchen:
            raise serializers.ValidationError({"kitchen_photo_urls": "Home chefs must upload kitchen photos."})
        return attrs


class RegisterProviderSerializer(ProviderSerializer):
    class Meta(ProviderSerializer.Meta):
        extra_kwargs = {"nid_number": {"required": True}, "photo_url": {"required": True}, "nid_front_url": {"required": True}}


class PublicProviderSerializer(serializers.ModelSerializer):
    trust_score = serializers.IntegerField(read_only=True)

    class Meta:
        model = Provider
        fields = [
            "id", "full_name", "provider_type", "bio", "experience_years", "photo_url", "rating_avg", "rating_count",
            "jobs_completed", "badges", "trust_score", "approved_at",
        ]


class JobLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobLog
        fields = ["status", "note", "actor", "created_at"]


class JobSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.full_name", read_only=True, default="")
    logs = JobLogSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = [
            "id", "source", "source_id", "title", "category_slug", "area_id", "area_name", "address_line", "latitude",
            "longitude", "customer_name", "customer_phone", "scheduled_date", "slot", "amount", "is_emergency",
            "description", "photo_urls", "checklist", "before_photos", "after_photos", "provider_note", "status",
            "provider", "provider_name", "accepted_at", "started_at", "completed_at", "created_at", "logs",
        ]
        read_only_fields = fields


class OpenJobSerializer(JobSerializer):
    """Before a provider takes a job they see the work, not the customer's contact details."""

    class Meta(JobSerializer.Meta):
        fields = [f for f in JobSerializer.Meta.fields if f not in ("customer_phone", "address_line", "logs")]


class AdvanceSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[Job.Status.ON_THE_WAY, Job.Status.WORKING, Job.Status.COMPLETED])
    arrival_code = serializers.CharField(required=False, allow_blank=True, max_length=4)
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    photos = serializers.ListField(child=serializers.CharField(max_length=500), required=False, max_length=10)
    checklist = serializers.ListField(child=serializers.DictField(), required=False)


class EarningSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source="job.title", read_only=True)

    class Meta:
        model = Earning
        fields = ["id", "job", "job_title", "gross", "commission", "bonus", "net", "status", "payout", "created_at"]


class PayoutSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.full_name", read_only=True)

    class Meta:
        model = Payout
        fields = ["id", "provider", "provider_name", "amount", "method", "account", "status", "reference", "created_at", "paid_at"]
        read_only_fields = fields


class LocationSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)


class ReviewSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source="job.title", read_only=True)
    source = serializers.CharField(write_only=True)
    source_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Review
        fields = ["id", "job_title", "rating", "comment", "created_at", "source", "source_id"]
        read_only_fields = ["id", "job_title", "created_at"]
