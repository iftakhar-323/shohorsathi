from django.conf import settings
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from shohor_common.permissions import token_role
from shohor_common.roles import ADMIN

from .models import MediaFile

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
        media = MediaFile.objects.create(
            owner_user_id=request.user.id,
            file=v["file"],
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
        if media.visibility == MediaFile.Visibility.PRIVATE and str(media.owner_user_id) != str(request.user.id):
            if token_role(request) != ADMIN:
                raise PermissionDenied()
        return FileResponse(media.file.open("rb"), content_type=media.content_type)
