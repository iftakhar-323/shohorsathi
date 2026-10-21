import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from shohor_common.testing import auth_client

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def upload(client, **fields):
    return client.post("/api/media/", {"file": SimpleUploadedFile("a.png", PNG, "image/png"), **fields}, format="multipart")


@pytest.mark.django_db
def test_public_upload_returns_media_url():
    res = upload(auth_client(user_id=1), purpose="problem_photo")
    assert res.status_code == 201
    assert res.data["url"].startswith("/media/public/problem_photo/")


@pytest.mark.django_db
def test_nid_is_forced_private_and_only_owner_or_admin_can_read():
    res = upload(auth_client(user_id=1), purpose="nid", visibility="public")
    assert res.data["visibility"] == "private"
    url = res.data["url"]
    assert auth_client(user_id=1).get(url).status_code == 200
    assert auth_client(user_id=2).get(url).status_code == 403
    assert auth_client("admin", user_id=3).get(url).status_code == 200


@pytest.mark.django_db
def test_rejects_unknown_type_and_anonymous():
    from rest_framework.test import APIClient

    bad = auth_client().post(
        "/api/media/", {"file": SimpleUploadedFile("a.exe", b"MZ", "application/x-msdownload")}, format="multipart"
    )
    assert bad.status_code == 400
    assert upload(APIClient()).status_code == 401
