from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenViewBase
from shohor_common.internal import IsInternal
from shohor_common.permissions import IsAdmin

from . import otp, privacy
from .models import Address, Area, HomeProfile, HomeReminder, OtpCode, User
from .serializers import (
    AddressSerializer,
    AdminUserSerializer,
    AreaSerializer,
    HomeProfileSerializer,
    HomeReminderSerializer,
    OtpRequestSerializer,
    PasswordResetSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .tokens import LoginSerializer, RefreshSerializer, token_pair


class OtpThrottle(AnonRateThrottle):
    """OTP requests per IP; each SMS costs money and invites abuse."""

    def get_rate(self):
        return settings.OTP_THROTTLE_RATE


class OtpRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OtpThrottle]

    def post(self, request):
        data = OtpRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        phone, purpose = data.validated_data["phone"], data.validated_data["purpose"]
        channel = data.validated_data.get("channel", "sms")
        # Do not reveal whether a number is registered: reset requests for unknown numbers look the same.
        if purpose == OtpCode.Purpose.RESET_PASSWORD and not User.objects.filter(phone=phone).exists():
            return Response({"detail": "Code sent."})
        try:
            otp.issue(phone, purpose, channel=channel)
        except otp.OtpError as e:
            return Response({"detail": str(e)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        return Response({"detail": "Code sent."})


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        data = RegisterSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        try:
            otp.consume(v["phone"], OtpCode.Purpose.REGISTER, v["otp"])
        except otp.OtpError as e:
            return Response({"otp": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.create_user(
            phone=v["phone"],
            password=v["password"],
            full_name=v["full_name"],
            email=v.get("email", ""),
            is_phone_verified=True,
            terms_version=settings.TERMS_VERSION,
            terms_accepted_at=timezone.now(),
            marketing_opt_in=v.get("marketing_opt_in", False),
        )
        return Response({"user": UserSerializer(user).data, **token_pair(user)}, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class RefreshView(TokenViewBase):
    serializer_class = RefreshSerializer


class PasswordResetView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = PasswordResetSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        try:
            otp.consume(v["phone"], OtpCode.Purpose.RESET_PASSWORD, v["otp"])
            user = User.objects.get(phone=v["phone"])
        except (otp.OtpError, User.DoesNotExist):
            return Response({"otp": ["Code expired or incorrect."]}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(v["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": "Password updated."})


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class ExportView(APIView):
    """Everything ShohorSathi holds about me, as one JSON file."""

    def get(self, request):
        response = Response(privacy.export(request.user))
        response["Content-Disposition"] = 'attachment; filename="shohorsathi-my-data.json"'
        return response


class DeleteAccountView(APIView):
    def post(self, request):
        if not authenticate(request, phone=request.user.phone, password=request.data.get("password", "")):
            return Response({"password": ["Password is incorrect."]}, status=status.HTTP_400_BAD_REQUEST)
        privacy.delete_account(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AreaListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = AreaSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Area.objects.filter(is_active=True)
        city = self.request.query_params.get("city")
        return qs.filter(city__iexact=city) if city else qs


class CityListView(APIView):
    """Cities with at least one active area: launching a city is just adding its areas."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(sorted(set(Area.objects.filter(is_active=True).values_list("city", flat=True))))


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    pagination_class = None

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user).select_related("area")

    @transaction.atomic
    def perform_create(self, serializer):
        self._save(serializer, user=self.request.user)

    @transaction.atomic
    def perform_update(self, serializer):
        self._save(serializer)

    def _save(self, serializer, **extra):
        address = serializer.save(**extra)
        if address.is_default:
            self.get_queryset().exclude(pk=address.pk).update(is_default=False)


class AdminAreaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AreaSerializer
    queryset = Area.objects.all()
    pagination_class = None


class AdminUserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        qs = User.objects.order_by("-date_joined")
        params = self.request.query_params
        if role := params.get("role"):
            qs = qs.filter(role=role)
        if q := params.get("q"):
            qs = qs.filter(phone__contains=q) | qs.filter(full_name__icontains=q)
        return qs

    @action(detail=True, methods=["post"])
    def block(self, request, pk=None):
        return self._set_active(False)

    @action(detail=True, methods=["post"])
    def unblock(self, request, pk=None):
        return self._set_active(True)

    def _set_active(self, active):
        user = self.get_object()
        if user == self.request.user:
            return Response({"detail": "You cannot block yourself."}, status=status.HTTP_400_BAD_REQUEST)
        user.is_active = active
        user.save(update_fields=["is_active"])
        return Response(AdminUserSerializer(user).data)


class InternalUserView(APIView):
    permission_classes = [IsInternal]
    authentication_classes = []

    def get(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if user is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response({"id": user.id, "phone": user.phone, "full_name": user.full_name, "email": user.email, "role": user.role})


class InternalUserByPhoneView(APIView):
    permission_classes = [IsInternal]
    authentication_classes = []

    def get(self, request, phone):
        user = User.objects.filter(phone=phone, is_active=True).first()
        if user is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response({"id": user.id, "phone": user.phone, "full_name": user.full_name})


class InternalUserIdsView(APIView):
    """Active user ids by role, for broadcasts."""

    permission_classes = [IsInternal]
    authentication_classes = []

    def get(self, request):
        qs = User.objects.filter(is_active=True)
        if role := request.query_params.get("role"):
            qs = qs.filter(role__in=role.split(","))
        return Response({"ids": list(qs.values_list("id", flat=True))})


class HomeProfileViewSet(viewsets.ModelViewSet):
    serializer_class = HomeProfileSerializer

    def get_queryset(self):
        return HomeProfile.objects.filter(user=self.request.user).prefetch_related("reminders").select_related("area")

    def perform_create(self, serializer):
        profile = serializer.save(user=self.request.user)
        today = timezone.localdate()
        from datetime import timedelta
        if profile.ac_count > 0:
            HomeReminder.objects.create(
                home=profile,
                title_en="Pre-Summer AC Master Servicing",
                title_bn="গ্রীষ্মপূর্ব এসি মাস্টার সার্ভিসিং",
                category_slug="ac",
                recommended_service_slug="ac-cleaning",
                due_date=today + timedelta(days=90),
                frequency_days=180,
                notes="ঠান্ডা ঠিক রাখতে প্রতি ৬ মাসে সার্ভিসিং করানো ভালো।",
            )
        if profile.water_purifier:
            HomeReminder.objects.create(
                home=profile,
                title_en="Water Purifier Filter & Candle Replacement",
                title_bn="ওয়াটার ফিল্টার ক্যান্ডেল পরিবর্তন",
                category_slug="plumbing",
                recommended_service_slug="plumber-visit",
                due_date=today + timedelta(days=60),
                frequency_days=90,
                notes="বিশুদ্ধ পানির জন্য সেডিমেন্ট ও কার্বন ফিল্টার বদলান।",
            )

    @action(detail=True, methods=["get"])
    def health(self, request, pk=None):
        profile = self.get_object()
        return Response({
            "health_score": profile.health_score,
            "wiring_age_years": profile.wiring_age_years,
            "plumbing_age_years": profile.plumbing_age_years,
            "overdue_reminders": profile.reminders.filter(is_completed=False, due_date__lt=timezone.localdate()).count(),
        })

    @action(detail=True, methods=["post"], url_path="add-reminder")
    def add_reminder(self, request, pk=None):
        profile = self.get_object()
        serializer = HomeReminderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reminder = serializer.save(home=profile)
        return Response(HomeReminderSerializer(reminder).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="complete-reminder/(?P<reminder_id>[^/.]+)")
    def complete_reminder(self, request, pk=None, reminder_id=None):
        profile = self.get_object()
        reminder = profile.reminders.filter(id=reminder_id).first()
        if not reminder:
            return Response({"detail": "Reminder not found."}, status=status.HTTP_404_NOT_FOUND)
        reminder.complete()
        return Response(HomeReminderSerializer(reminder).data)
