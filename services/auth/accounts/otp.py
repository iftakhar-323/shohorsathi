import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from shohor_common import events

from .models import OtpCode

log = logging.getLogger(__name__)


class OtpError(Exception):
    pass


def _hash(code):
    return hmac.new(settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()


def issue(phone, purpose, channel="sms"):
    last = OtpCode.objects.filter(phone=phone, purpose=purpose).order_by("-created_at").first()
    now = timezone.now()
    if last and (now - last.created_at).total_seconds() < settings.OTP_RESEND_SECONDS:
        raise OtpError("Please wait before requesting another code.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    OtpCode.objects.create(
        phone=phone,
        purpose=purpose,
        code_hash=_hash(code),
        expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
    )
    if settings.OTP_DEBUG:
        log.info("OTP for %s (%s) [%s]: %s", phone, purpose, channel, code)
    try:
        events.publish("otp.requested", {"phone": phone, "purpose": purpose, "code": code, "channel": channel})
    except Exception as e:
        log.warning("failed to publish otp.requested: %s", e)
    return code


def consume(phone, purpose, code):
    otp = (
        OtpCode.objects.filter(phone=phone, purpose=purpose, used_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if otp is None or otp.expires_at < timezone.now():
        raise OtpError("Code expired or not requested.")
    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise OtpError("Too many attempts. Request a new code.")
    if not hmac.compare_digest(otp.code_hash, _hash(code)):
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        raise OtpError("Incorrect code.")
    otp.used_at = timezone.now()
    otp.save(update_fields=["used_at"])
