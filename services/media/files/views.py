from django.conf import settings
from django.core.files.base import ContentFile
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from shohor_common.internal import IsInternal
from shohor_common.permissions import IsAdmin, token_role
from shohor_common.roles import ADMIN

from . import crypto
from .models import MediaAccess, MediaFile

# Identity documents are never public, whatever the client asks for.
ALWAYS_PRIVATE = {MediaFile.Purpose.NID}
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf", "video/mp4", "audio/webm", "audio/mpeg"}


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    purpose = serializers.ChoiceField(choices=MediaFile.Purpose.choices, default=MediaFile.Purpose.OTHER)
    visibility = serializers.ChoiceField(choices=MediaFile.Visibility.choices, default=MediaFile.Visibility.PUBLIC)

    def validate_file(self, f):
        if f.size > settings.MEDIA_MAX_BYTES:
            raise serializers.ValidationError(f"File is larger than {settings.MEDIA_MAX_BYTES // (1024 * 1024)} MB.")
        if f.content_type not in ALLOWED_TYPES:
            raise serializers.ValidationError("Only images, PDF, MP4 video or audio are allowed.")
        return f


def file_url(media):
    if media.visibility == MediaFile.Visibility.PUBLIC:
        return settings.MEDIA_URL + media.file.name
    return f"/api/media/{media.id}/download/"


class UploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        data = UploadSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        visibility = MediaFile.Visibility.PRIVATE if v["purpose"] in ALWAYS_PRIVATE else v["visibility"]
        private = visibility == MediaFile.Visibility.PRIVATE
        upload = ContentFile(crypto.encrypt(v["file"].read()), name=v["file"].name) if private else v["file"]
        media = MediaFile.objects.create(
            owner_user_id=request.user.id,
            file=upload,
            encrypted=private,
            visibility=visibility,
            purpose=v["purpose"],
            original_name=v["file"].name[:255],
            content_type=v["file"].content_type,
            size=v["file"].size,
        )
        return Response(
            {"id": media.id, "url": file_url(media), "visibility": visibility, "content_type": media.content_type},
            status=status.HTTP_201_CREATED,
        )


class DownloadView(APIView):
    def get(self, request, pk):
        media = get_object_or_404(MediaFile, pk=pk)
        owner = str(media.owner_user_id) == str(request.user.id)
        if media.visibility == MediaFile.Visibility.PRIVATE and not owner and token_role(request) != ADMIN:
            raise PermissionDenied()
        if media.visibility == MediaFile.Visibility.PRIVATE:
            MediaAccess.objects.create(media=media, user_id=request.user.id, role=token_role(request) or "", ip=request.META.get("REMOTE_ADDR"))
        if media.encrypted:
            with media.file.open("rb") as f:
                return HttpResponse(crypto.decrypt(f.read()), content_type=media.content_type)
        return FileResponse(media.file.open("rb"), content_type=media.content_type)


def delete_files(qs):
    n = 0
    for media in qs:
        media.file.delete(save=False)
        media.delete()
        n += 1
    return n


class InternalDeleteView(APIView):
    """Other services delete documents they no longer may keep (retention, account deletion)."""

    permission_classes = [IsInternal]
    authentication_classes = []

    def post(self, request):
        ids, paths = [], []
        for url in request.data.get("urls", []):
            if url.startswith("/api/media/"):
                ids.append(int(url.split("/")[3]))
            elif url.startswith(settings.MEDIA_URL):
                paths.append(url[len(settings.MEDIA_URL):])
        deleted = delete_files(MediaFile.objects.filter(id__in=ids)) + delete_files(MediaFile.objects.filter(file__in=paths))
        return Response({"deleted": deleted})


class AccessLogView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        rows = MediaAccess.objects.filter(media_id=pk)[:200]
        return Response([{"user_id": r.user_id, "role": r.role, "ip": r.ip, "at": r.created_at} for r in rows])
