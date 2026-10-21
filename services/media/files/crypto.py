"""Encryption at rest for private uploads (Fernet: AES-128-CBC + HMAC-SHA256)."""
import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings


def _fernet():
    key = settings.MEDIA_ENCRYPTION_KEY
    if not key:
        # Development only: derive a stable key from the secret key. Production sets MEDIA_ENCRYPTION_KEY.
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)


def encrypt(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt(data: bytes) -> bytes:
    return _fernet().decrypt(data)
