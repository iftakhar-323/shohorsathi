from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from shohor_common.permissions import IsAdmin

from . import logic
from .models import Broadcast, Notification, SmsLog


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "title_bn", "title_en", "body_bn", "body_en", "link", "app", "read_at", "created_at"]


class BroadcastSerializer(serializers.ModelSerializer):
    audience = serializers.ChoiceField(choices=["customers", "providers", "all"])

    class Meta:
        model = Broadcast
        fields = ["id", "audience", "title_bn", "title_en", "body_bn", "body_en", "link", "sent_count", "created_at"]
        read_only_fields = ["id", "sent_count", "created_at"]


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        qs = Notification.objects.filter(user_id=self.request.user.id)
        if app := self.request.query_params.get("app"):
            qs = qs.filter(app=app)
        return qs

    @action(detail=False, url_path="unread-count")
    def unread_count(self, request):
        return Response({"unread": self.get_queryset().filter(read_at__isnull=True).count()})

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        self.get_queryset().filter(pk=pk, read_at__isnull=True).update(read_at=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)


class BroadcastView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(BroadcastSerializer(Broadcast.objects.order_by("-created_at")[:50], many=True).data)

    def post(self, request):
        data = BroadcastSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(BroadcastSerializer(logic.broadcast(dict(data.validated_data))).data, status=status.HTTP_201_CREATED)


class SmsLogView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        rows = SmsLog.objects.all()[:100]
        return Response([{"phone": r.phone, "body": r.body, "status": r.status, "created_at": r.created_at} for r in rows])
