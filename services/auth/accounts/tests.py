import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts import otp
from accounts.models import Area, User

PHONE = "01712345678"


@pytest.fixture
def client():
    return APIClient()


def register(client, phone=PHONE):
    code = otp.issue(phone, "register")
    return client.post(
        "/api/auth/register/",
        {"phone": phone, "full_name": "Rahim", "password": "strong-pass-123", "otp": code},
        format="json",
    )


@pytest.mark.django_db
def test_register_with_otp_returns_tokens_with_role(client):
    res = register(client)
    assert res.status_code == 201
    assert AccessToken(res.data["access"])["role"] == "customer"
    assert User.objects.get(phone=PHONE).is_phone_verified


@pytest.mark.django_db
def test_register_rejects_wrong_otp(client):
    otp.issue(PHONE, "register")
    res = client.post(
        "/api/auth/register/",
        {"phone": PHONE, "full_name": "Rahim", "password": "strong-pass-123", "otp": "000000"},
        format="json",
    )
    assert res.status_code == 400
    assert not User.objects.exists()


@pytest.mark.django_db
def test_register_rejects_invalid_phone(client):
    res = client.post("/api/auth/otp/request/", {"phone": "12345", "purpose": "register"}, format="json")
    assert res.status_code == 400


@pytest.mark.django_db
def test_login_and_me(client):
    register(client)
    res = client.post("/api/auth/login/", {"phone": PHONE, "password": "strong-pass-123"}, format="json")
    assert res.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
    me = client.get("/api/me/")
    assert me.data["phone"] == PHONE
    assert me.data["role"] == "customer"


@pytest.mark.django_db
def test_password_reset(client):
    register(client)
    code = otp.issue(PHONE, "reset_password")
    res = client.post(
        "/api/auth/password/reset/",
        {"phone": PHONE, "otp": code, "new_password": "another-pass-456"},
        format="json",
    )
    assert res.status_code == 200
    assert User.objects.get(phone=PHONE).check_password("another-pass-456")


@pytest.mark.django_db
def test_only_one_default_address(client):
    tokens = register(client).data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    area = Area.objects.create(name_en="Mirpur", name_bn="মিরপুর")
    first = client.post("/api/me/addresses/", {"area": area.id, "line": "Road 1", "is_default": True}, format="json")
    client.post("/api/me/addresses/", {"area": area.id, "line": "Road 2", "is_default": True}, format="json")
    addresses = client.get("/api/me/addresses/").data
    assert [a["is_default"] for a in addresses] == [True, False]
    assert addresses[1]["id"] == first.data["id"]
