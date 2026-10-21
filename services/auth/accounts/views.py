from django.db import transaction
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenViewBase
from shohor_common.internal import IsInternal
from shohor_common.permissions import IsAdmin

from . import otp
from .models import Address, Area, OtpCode, User
from .serializers import (
    AddressSerializer,
    AreaSerializer,
    OtpRequestSerializer,
    PasswordResetSerializer,
    AdminUserSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .tokens import LoginSerializer, RefreshSerializer, token_pair


class OtpThrottle(AnonRateThrottle):
    rate = "10/hour"


class OtpRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OtpThrottle]

    def post(self, request):
        data = OtpRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        phone, purpose = data.validated_data["phone"], data.validated_data["purpose"]
        # Do not reveal whether a number is registered: reset requests for unknown numbers look the same.
        if purpose == OtpCode.Purpose.RESET_PASSWORD and not User.objects.filter(phone=phone).exists():
            return Response({"detail": "Code sent."})
        try:
            otp.issue(phone, purpose)
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


class AreaListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = AreaSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Area.objects.filter(is_active=True)
        city = self.request.query_params.get("city")
        return qs.filter(city__iexact=city) if city else qs


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


class InternalUserIdsView(APIView):
    """Active user ids by role, for broadcasts."""

    permission_classes = [IsInternal]
    authentication_classes = []

    def get(self, request):
        qs = User.objects.filter(is_active=True)
        if role := request.query_params.get("role"):
            qs = qs.filter(role__in=role.split(","))
        return Response({"ids": list(qs.values_list("id", flat=True))})
