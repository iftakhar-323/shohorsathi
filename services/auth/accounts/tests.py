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


@pytest.mark.django_db
def test_refresh_picks_up_role_change(client):
    tokens = register(client).data
    from accounts.tasks import provider_approved

    provider_approved({"user_id": User.objects.get(phone=PHONE).id})
    res = client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
    assert res.status_code == 200
    assert AccessToken(res.data["access"])["role"] == "provider"
    # the old refresh token is spent
    again = client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
    assert again.status_code == 401


@pytest.mark.django_db
def test_admin_blocks_user_and_blocked_user_cannot_refresh(client):
    tokens = register(client).data
    admin = User.objects.create_superuser(phone="01999999999", password="admin-pass-123", full_name="Admin")
    login = client.post("/api/auth/login/", {"phone": admin.phone, "password": "admin-pass-123"}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    target = User.objects.get(phone=PHONE)
    assert client.post(f"/api/admin/users/{target.id}/block/").data["is_active"] is False
    client.credentials()
    assert client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code == 401


@pytest.mark.django_db
def test_customer_cannot_manage_areas(client):
    tokens = register(client).data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert client.post("/api/admin/areas/", {"name_en": "X", "name_bn": "X"}, format="json").status_code == 403
