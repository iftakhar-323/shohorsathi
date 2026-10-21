from rest_framework import serializers
from shohor_common.permissions import token_role

from .models import (
    Earning,
    InsuranceClaim,
    InsuranceEnrollment,
    InsurancePlan,
    Job,
    JobLog,
    ModuleCompletion,
    Payout,
    Provider,
    Review,
    SafetyIncident,
    TrainingModule,
)


class ProviderSerializer(serializers.ModelSerializer):
    trust_score = serializers.IntegerField(read_only=True)

    class Meta:
        model = Provider
        fields = [
            "id", "user_id", "full_name", "phone", "gender", "provider_type", "skills", "area_ids", "bio",
            "experience_years", "nid_number", "photo_url", "nid_front_url", "nid_back_url", "kitchen_photo_urls",
            "status", "rejection_reason", "is_online", "working_days", "work_start", "work_end", "payout_method",
            "payout_account", "rating_avg", "rating_count", "jobs_completed", "badges", "trust_score", "created_at",
            "approved_at", "emergency_contact_name", "emergency_contact_phone",
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
    customer_score = serializers.SerializerMethodField()

    def get_customer_score(self, obj):
        from .trust import customer_score

        return customer_score(obj.user_id)

    def to_representation(self, obj):
        from .trust import contact_visible

        data = super().to_representation(obj)
        request = self.context.get("request")
        is_admin = request is not None and token_role(request) == "admin"
        if "customer_phone" in data and not is_admin and not contact_visible(obj):
            data["customer_phone"] = ""  # phone numbers only while the visit needs coordinating
        return data

    class Meta:
        model = Job
        fields = [
            "id", "source", "source_id", "title", "category_slug", "area_id", "area_name", "address_line", "latitude",
            "longitude", "customer_name", "customer_phone", "scheduled_date", "slot", "amount", "is_emergency",
            "description", "photo_urls", "checklist", "before_photos", "after_photos", "provider_note", "status",
            "provider", "provider_name", "accepted_at", "started_at", "completed_at", "created_at", "logs",
            "required_gender", "customer_rating", "customer_feedback", "customer_score",
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
        fields = ["id", "provider", "provider_name", "amount", "instant", "fee", "insurance_premium", "method", "account", "status", "reference", "created_at", "paid_at"]
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
        fields = ["id", "job_title", "rating", "comment", "created_at", "source", "source_id", "dispute", "dispute_note"]
        read_only_fields = ["id", "job_title", "created_at", "dispute", "dispute_note"]


class DisputeSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source="job.title", read_only=True)
    provider_name = serializers.CharField(source="provider.full_name", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "job_title", "provider_name", "rating", "comment", "dispute", "dispute_reason", "dispute_note", "hidden", "created_at"]


class SafetyIncidentSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source="job.title", read_only=True, default="")
    area_name = serializers.CharField(source="job.area_name", read_only=True, default="")
    customer = serializers.SerializerMethodField()
    provider = serializers.SerializerMethodField()

    class Meta:
        model = SafetyIncident
        fields = ["id", "job_title", "area_name", "role", "latitude", "longitude", "note", "status", "resolution", "customer", "provider", "created_at", "resolved_at"]

    def get_customer(self, obj):
        return {"name": obj.job.customer_name, "phone": obj.job.customer_phone} if obj.job else None

    def get_provider(self, obj):
        p = obj.job.provider if obj.job else None
        return {"name": p.full_name, "phone": p.phone, "emergency_contact": p.emergency_contact_phone} if p else None


class InsurancePlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsurancePlan
        fields = ["id", "name_bn", "name_en", "partner", "weekly_premium", "coverage_bn", "coverage_en", "is_active"]


class EnrollmentSerializer(serializers.ModelSerializer):
    plan = InsurancePlanSerializer(read_only=True)
    provider_name = serializers.CharField(source="provider.full_name", read_only=True)

    class Meta:
        model = InsuranceEnrollment
        fields = ["id", "plan", "provider_name", "status", "last_premium_week", "started_at"]


class ClaimSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="enrollment.provider.full_name", read_only=True)
    plan_name = serializers.CharField(source="enrollment.plan.name_en", read_only=True)

    class Meta:
        model = InsuranceClaim
        fields = ["id", "provider_name", "plan_name", "description", "photo_urls", "status", "amount", "note", "created_at"]
        read_only_fields = ["id", "provider_name", "plan_name", "status", "amount", "note", "created_at"]


class TrainingModuleSerializer(serializers.ModelSerializer):
    """Admin view: includes the answers."""

    class Meta:
        model = TrainingModule
        fields = ["id", "slug", "title_bn", "title_en", "body_bn", "body_en", "video_url", "category_slug", "questions", "pass_percent", "is_active", "sort_order"]

    def validate_questions(self, value):
        for q in value:
            if not q.get("options") or not 0 <= int(q.get("answer", -1)) < len(q["options"]):
                raise serializers.ValidationError("Each question needs options and the index of the right one.")
        return value


class ProviderModuleSerializer(serializers.ModelSerializer):
    """Provider view: the quiz without the answers, plus their own result."""

    questions = serializers.SerializerMethodField()
    result = serializers.SerializerMethodField()

    class Meta:
        model = TrainingModule
        fields = ["id", "slug", "title_bn", "title_en", "body_bn", "body_en", "video_url", "pass_percent", "questions", "result"]

    def get_questions(self, obj):
        return [{"q": q["q"], "options": q["options"]} for q in obj.questions]

    def get_result(self, obj):
        done = self.context.get("completions", {}).get(obj.id)
        return {"score": done.score, "passed": done.passed, "certificate_code": done.certificate_code, "attempts": done.attempts} if done else None
