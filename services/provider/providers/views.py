from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from shohor_common.internal import IsInternal
from shohor_common.permissions import IsAdmin

from . import logic, trust
from .models import (
    Earning,
    InsuranceClaim,
    InsuranceEnrollment,
    InsurancePlan,
    Job,
    ModuleCompletion,
    Payout,
    Provider,
    Review,
    SafetyIncident,
    TrainingModule,
)
from .serializers import (
    AdvanceSerializer,
    EarningSerializer,
    JobSerializer,
    LocationSerializer,
    OpenJobSerializer,
    PayoutSerializer,
    ProviderSerializer,
    PublicProviderSerializer,
    ClaimSerializer,
    DisputeSerializer,
    EnrollmentSerializer,
    InsurancePlanSerializer,
    ProviderModuleSerializer,
    RegisterProviderSerializer,
    ReviewSerializer,
    SafetyIncidentSerializer,
    TrainingModuleSerializer,
)

S = Job.Status
ACTIVE = [S.ASSIGNED, S.ACCEPTED, S.ON_THE_WAY, S.WORKING]


def current_provider(request, approved=True):
    provider = Provider.objects.filter(user_id=request.user.id).first()
    if provider is None:
        raise NotFound("You have not registered as a provider yet.")
    if approved and provider.status != Provider.Status.APPROVED:
        raise PermissionDenied("Your provider account is not approved yet.")
    return provider


class RegisterView(APIView):
    def post(self, request):
        if Provider.objects.filter(user_id=request.user.id).exists():
            return Response({"detail": "You have already applied."}, status=status.HTTP_400_BAD_REQUEST)
        data = RegisterProviderSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        provider = data.save(
            user_id=request.user.id,
            full_name=request.auth.get("name", ""),
            phone=request.auth.get("phone", ""),
        )
        return Response(ProviderSerializer(provider).data, status=status.HTTP_201_CREATED)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = ProviderSerializer

    def get_object(self):
        return current_provider(self.request, approved=False)

    def perform_update(self, serializer):
        provider = serializer.instance
        # Changing identity documents after rejection sends the application back for review.
        resubmit = provider.status == Provider.Status.REJECTED and any(
            f in serializer.validated_data for f in ("nid_number", "nid_front_url", "photo_url", "kitchen_photo_urls")
        )
        serializer.save(**({"status": Provider.Status.PENDING} if resubmit else {}))


class LocationView(APIView):
    def post(self, request):
        provider = current_provider(request)
        data = LocationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        provider.last_latitude = data.validated_data["latitude"]
        provider.last_longitude = data.validated_data["longitude"]
        provider.location_updated_at = timezone.now()
        provider.save(update_fields=["last_latitude", "last_longitude", "location_updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class JobViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """?tab=available (open jobs matching my areas and skills) | active | history"""

    def provider(self):
        return current_provider(self.request)

    def get_queryset(self):
        provider = self.provider()
        tab = self.request.query_params.get("tab", "active")
        if tab == "available":
            return logic.available_jobs(provider)
        mine = Job.objects.filter(provider=provider).prefetch_related("logs")
        if tab == "history":
            return mine.filter(status__in=[S.COMPLETED, S.CANCELLED]).order_by("-updated_at")
        return mine.filter(status__in=ACTIVE)

    def get_object(self):
        provider = self.provider()
        job = get_object_or_404(Job, pk=self.kwargs["pk"])
        if job.provider_id != provider.id and not logic.available_jobs(provider).filter(pk=job.pk).exists():
            raise NotFound()
        return job

    def get_serializer_class(self):
        if self.action == "list" and self.request.query_params.get("tab") == "available":
            return OpenJobSerializer
        return JobSerializer

    def retrieve(self, request, pk=None):
        job = self.get_object()
        cls = JobSerializer if job.provider_id == self.provider().id else OpenJobSerializer
        return Response(cls(job).data)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        return Response(JobSerializer(logic.accept(self.get_object(), self.provider())).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return Response(OpenJobSerializer(logic.reject(self.get_object(), self.provider())).data)

    @action(detail=True, methods=["patch"])
    def status(self, request, pk=None):
        data = AdvanceSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        job = logic.advance(self.get_object(), self.provider(), **data.validated_data)
        return Response(JobSerializer(job).data)

    @action(detail=True, methods=["post"], url_path="rate-customer")
    def rate_customer(self, request, pk=None):
        job = trust.rate_customer(self.get_object(), self.provider(), request.data.get("rating", 0), request.data.get("feedback", ""))
        return Response(JobSerializer(job).data)


class EarningsView(APIView):
    def get(self, request):
        provider = current_provider(request)
        recent = provider.earnings.select_related("job")[:50]
        return Response({"summary": logic.earnings_summary(provider), "earnings": EarningSerializer(recent, many=True).data})


class PayoutViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = PayoutSerializer

    def get_queryset(self):
        return current_provider(self.request).payouts.all()

    def create(self, request):
        payout = logic.request_payout(current_provider(request))
        return Response(PayoutSerializer(payout).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def instant(self, request):
        """Cash out now for a fee instead of waiting for Sunday."""
        payout = logic.request_payout(current_provider(request), instant=True)
        return Response(PayoutSerializer(payout).data, status=status.HTTP_201_CREATED)


class PublicProviderView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicProviderSerializer
    queryset = Provider.objects.filter(status=Provider.Status.APPROVED)


class JobLocationView(APIView):
    """Live tracking for the customer of a job: the assigned provider's last known position."""

    def get(self, request, source, source_id):
        job = get_object_or_404(Job, source=source, source_id=source_id, user_id=request.user.id)
        p = job.provider
        if p is None or job.status not in (S.ON_THE_WAY, S.WORKING) or p.last_latitude is None:
            return Response({"available": False, "status": job.status})
        return Response(
            {
                "available": True,
                "status": job.status,
                "provider_name": p.full_name,
                "latitude": str(p.last_latitude),
                "longitude": str(p.last_longitude),
                "updated_at": p.location_updated_at,
                "destination": {"latitude": job.latitude, "longitude": job.longitude},
            }
        )


# ---- admin ---------------------------------------------------------------------------------

class AdminProviderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = ProviderSerializer

    def get_queryset(self):
        qs = Provider.objects.all()
        params = self.request.query_params
        if s := params.get("status"):
            qs = qs.filter(status=s)
        if t := params.get("type"):
            qs = qs.filter(provider_type=t)
        if area := params.get("area"):
            qs = qs.filter(area_ids__contains=[int(area)])
        return logic.search_q(qs, params.get("q"))

    def _review(self, decision):
        provider = logic.review_provider(self.get_object(), decision, self.request.data.get("reason", ""))
        return Response(ProviderSerializer(provider).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._review("approve")

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        if not request.data.get("reason"):
            return Response({"reason": ["Tell the applicant why."]}, status=status.HTTP_400_BAD_REQUEST)
        return self._review("reject")

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        return self._review("suspend")


class AdminJobViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = JobSerializer

    def get_queryset(self):
        qs = Job.objects.select_related("provider").prefetch_related("logs").order_by("-is_emergency", "-created_at")
        params = self.request.query_params
        if s := params.get("status"):
            qs = qs.filter(status=s)
        if src := params.get("source"):
            qs = qs.filter(source=src)
        return qs

    @action(detail=True)
    def suggestions(self, request, pk=None):
        providers = logic.suggest_providers(self.get_object())
        return Response(ProviderSerializer(providers, many=True).data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        provider = get_object_or_404(Provider, pk=request.data.get("provider_id"))
        return Response(JobSerializer(logic.assign(self.get_object(), provider)).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        job = self.get_object()
        if job.status in (S.COMPLETED, S.CANCELLED):
            return Response({"detail": "Job already closed."}, status=status.HTTP_400_BAD_REQUEST)
        logic.set_status(job, S.CANCELLED, request.data.get("reason", "Cancelled by admin"), actor="admin")
        return Response(JobSerializer(job).data)


class AdminPayoutViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = PayoutSerializer

    def get_queryset(self):
        qs = Payout.objects.select_related("provider")
        if s := self.request.query_params.get("status"):
            qs = qs.filter(status=s)
        return qs

    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, pk=None):
        reference = request.data.get("reference", "")
        if not reference:
            return Response({"reference": ["Enter the bKash/Nagad transaction id."]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PayoutSerializer(logic.mark_payout_paid(self.get_object(), reference)).data)


class AdminStatsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(
            {
                "providers_by_status": dict(Provider.objects.values_list("status").annotate(n=Count("id"))),
                "jobs_by_status": dict(Job.objects.values_list("status").annotate(n=Count("id"))),
                "online_now": Provider.objects.filter(is_online=True, status=Provider.Status.APPROVED).count(),
                "payouts_requested": Payout.objects.filter(status=Payout.Status.REQUESTED).count(),
                "earnings_pending": Earning.objects.filter(status=Earning.Status.PENDING).count(),
            }
        )


class InternalProviderView(APIView):
    """Lookup by user id for other services (e.g. subscriptions pinning the same cleaner)."""

    permission_classes = [IsInternal]
    authentication_classes = []

    def get(self, request, user_id):
        provider = get_object_or_404(Provider, user_id=user_id)
        return Response(PublicProviderSerializer(provider).data | {"user_id": provider.user_id, "phone": provider.phone})


class ReviewView(APIView):
    def get(self, request):
        """Has the current customer reviewed this job? ?source=&source_id="""
        review = Review.objects.filter(
            user_id=request.user.id, job__source=request.query_params.get("source"), job__source_id=request.query_params.get("source_id")
        ).first()
        return Response(ReviewSerializer(review).data if review else None)

    def post(self, request):
        data = ReviewSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        review = logic.create_review(request.user.id, v["source"], v["source_id"], v["rating"], v.get("comment", ""))
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)


class PublicReviewsView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ReviewSerializer

    def get_queryset(self):
        return Review.objects.filter(provider_id=self.kwargs["pk"], provider__status=Provider.Status.APPROVED, hidden=False).select_related("job")


class InternalJobBySourceView(APIView):
    """Who are the customer and provider of a job? Used by chat to decide who may talk."""

    permission_classes = [IsInternal]
    authentication_classes = []

    def get(self, request, source, source_id):
        job = get_object_or_404(Job.objects.select_related("provider"), source=source, source_id=source_id)
        return Response({"job_id": job.id, "title": job.title, "status": job.status, "customer_user_id": job.user_id,
                         "provider_user_id": job.provider.user_id if job.provider else None,
                         "provider_name": job.provider.full_name if job.provider else ""})



# ---- trust & safety ----------------------------------------------------------------------------

class SosView(APIView):
    """Either side of a job can press SOS; admins are alerted at once (SMS + notification)."""

    def post(self, request):
        d = request.data
        incident = trust.raise_sos(request.user.id, d.get("source", ""), int(d.get("source_id", 0)), d.get("latitude"), d.get("longitude"), d.get("note", ""))
        return Response({"id": incident.id, "status": incident.status}, status=status.HTTP_201_CREATED)


class ShareView(APIView):
    def post(self, request):
        link = trust.create_share(request.user.id, request.data.get("source", ""), int(request.data.get("source_id", 0)))
        return Response({"token": link.token, "expires_at": link.expires_at}, status=status.HTTP_201_CREATED)


class SharedJobView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        return Response(trust.shared_view(token))


class DisputeView(APIView):
    def post(self, request, pk):
        review = get_object_or_404(Review, pk=pk)
        return Response(ReviewSerializer(trust.dispute_review(review, current_provider(request), request.data.get("reason", ""))).data)


class InsuranceView(APIView):
    def get(self, request):
        provider = current_provider(request)
        enrollment = trust.active_enrollment(provider)
        claims = InsuranceClaim.objects.filter(enrollment__provider=provider)
        return Response({
            "plans": InsurancePlanSerializer(InsurancePlan.objects.filter(is_active=True), many=True).data,
            "enrollment": EnrollmentSerializer(enrollment).data if enrollment else None,
            "claims": ClaimSerializer(claims, many=True).data,
        })

    def post(self, request):
        plan = get_object_or_404(InsurancePlan, pk=request.data.get("plan"))
        return Response(EnrollmentSerializer(trust.enroll(current_provider(request), plan)).data, status=status.HTTP_201_CREATED)

    def delete(self, request):
        enrollment = trust.active_enrollment(current_provider(request))
        if enrollment:
            enrollment.status = InsuranceEnrollment.Status.CANCELLED
            enrollment.save(update_fields=["status"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClaimView(APIView):
    def post(self, request):
        claim = trust.file_claim(current_provider(request), request.data.get("description", ""), request.data.get("photo_urls", []))
        return Response(ClaimSerializer(claim).data, status=status.HTTP_201_CREATED)


class TrainingView(APIView):
    def get(self, request):
        provider = current_provider(request)
        completions = {c.module_id: c for c in provider.trainings.all()}
        modules = trust.modules_for(provider)
        return Response(ProviderModuleSerializer(modules, many=True, context={"completions": completions}).data)


class QuizView(APIView):
    def post(self, request, slug):
        provider = current_provider(request)
        module = get_object_or_404(TrainingModule, slug=slug, is_active=True)
        c = trust.submit_quiz(provider, module, request.data.get("answers", []))
        return Response({"score": c.score, "passed": c.passed, "certificate_code": c.certificate_code, "attempts": c.attempts})


class CertificateView(APIView):
    """Anyone can verify a training certificate by its code."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, code):
        c = get_object_or_404(ModuleCompletion.objects.select_related("provider", "module"), certificate_code=code, passed=True)
        return Response({"provider": c.provider.full_name, "module": {"bn": c.module.title_bn, "en": c.module.title_en}, "score": c.score, "issued": c.completed_at})


class AdminSafetyViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = SafetyIncidentSerializer

    def get_queryset(self):
        qs = SafetyIncident.objects.select_related("job__provider")
        if s := self.request.query_params.get("status"):
            qs = qs.filter(status=s)
        return qs

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        return Response(SafetyIncidentSerializer(trust.resolve_incident(self.get_object(), request.data.get("resolution", ""))).data)


class AdminDisputeViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = DisputeSerializer

    def get_queryset(self):
        return Review.objects.filter(dispute=self.request.query_params.get("status", "open")).select_related("job", "provider")

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        review = get_object_or_404(Review, pk=pk)
        return Response(DisputeSerializer(trust.decide_dispute(review, bool(request.data.get("uphold")), request.data.get("note", ""))).data)


class AdminInsurancePlanViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = InsurancePlanSerializer
    queryset = InsurancePlan.objects.all()
    pagination_class = None


class AdminClaimViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = ClaimSerializer

    def get_queryset(self):
        qs = InsuranceClaim.objects.select_related("enrollment__provider", "enrollment__plan")
        if s := self.request.query_params.get("status"):
            qs = qs.filter(status=s)
        return qs

    @action(detail=True, methods=["post"])
    def update_status(self, request, pk=None):
        claim = self.get_object()
        new = request.data.get("status")
        if new not in InsuranceClaim.Status.values:
            return Response({"status": ["Unknown status."]}, status=status.HTTP_400_BAD_REQUEST)
        claim.status, claim.note = new, request.data.get("note", claim.note)
        if request.data.get("amount"):
            claim.amount = request.data["amount"]
        claim.save()
        return Response(ClaimSerializer(claim).data)


class AdminTrainingViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = TrainingModuleSerializer
    queryset = TrainingModule.objects.all()
    pagination_class = None
    lookup_field = "slug"
