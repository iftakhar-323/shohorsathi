from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def jwt_keypair():
    """A throwaway RS256 key pair so tests can sign tokens without the real keys mounted."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return private, public


def overrides(simple_jwt):
    """Overrides every service's settings_test applies: in-memory keys, captured events, eager Celery."""
    private, public = jwt_keypair()
    return {
        "SIMPLE_JWT": {**simple_jwt, "SIGNING_KEY": private, "VERIFYING_KEY": public},
        "INTERNAL_API_TOKEN": "dev-internal-token",
        "EVENTS_CAPTURE": True,
        "CELERY_TASK_ALWAYS_EAGER": True,
        "PASSWORD_HASHERS": ["django.contrib.auth.hashers.MD5PasswordHasher"],
        "CACHES": {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    }


def token(role="customer", user_id=1, **claims):
    from rest_framework_simplejwt.tokens import AccessToken

    t = AccessToken()
    t["user_id"] = user_id
    t["role"] = role
    t["name"] = claims.pop("name", f"User {user_id}")
    for k, v in claims.items():
        t[k] = v
    return str(t)


def auth_client(role="customer", user_id=1, **claims):
    from rest_framework.test import APIClient

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token(role, user_id, **claims)}")
    return client
