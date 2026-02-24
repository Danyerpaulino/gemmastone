from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.core.settings import get_settings


class OtpError(ValueError):
    pass


class OtpRateLimitError(OtpError):
    pass


class OtpVerificationError(OtpError):
    pass


@dataclass(frozen=True)
class JwtSession:
    token: str
    expires_at: datetime


def normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if not digits:
        return ""
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return f"+{digits}"


def request_otp(redis_client, phone: str) -> tuple[str, str]:
    settings = get_settings()
    normalized = normalize_phone(phone)
    if not normalized:
        raise OtpError("Invalid phone number.")

    rate_key = f"otp_rate:{normalized}"
    count = redis_client.incr(rate_key)
    if count == 1:
        redis_client.expire(rate_key, settings.otp_rate_window_seconds)
    if count > settings.otp_rate_limit:
        raise OtpRateLimitError("Too many OTP requests. Please try again later.")

    if settings.otp_length <= 0:
        raise OtpError("Invalid OTP length.")
    upper_bound = 10 ** settings.otp_length
    code = f"{secrets.randbelow(upper_bound):0{settings.otp_length}d}"
    payload = {"code": code, "attempts": 0}
    redis_client.setex(
        f"otp:{normalized}",
        settings.otp_ttl_seconds,
        json.dumps(payload),
    )
    return normalized, code


def verify_otp(redis_client, phone: str, code: str) -> str:
    settings = get_settings()
    normalized = normalize_phone(phone)
    if not normalized:
        raise OtpVerificationError("Invalid phone number.")

    key = f"otp:{normalized}"
    stored = redis_client.get(key)
    if not stored:
        raise OtpVerificationError("OTP expired or invalid.")

    payload = json.loads(stored)
    attempts = int(payload.get("attempts", 0))
    if attempts >= settings.otp_max_attempts:
        redis_client.delete(key)
        raise OtpVerificationError("OTP expired or invalid.")

    if str(code).strip() != str(payload.get("code")):
        payload["attempts"] = attempts + 1
        ttl = redis_client.ttl(key)
        ttl = ttl if ttl and ttl > 0 else settings.otp_ttl_seconds
        redis_client.setex(key, ttl, json.dumps(payload))
        raise OtpVerificationError("Incorrect verification code.")

    redis_client.delete(key)
    return normalized


def create_jwt_session(patient_id: str, provider_id: str | None) -> JwtSession:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.jwt_expiry_days)
    payload = {
        "sub": patient_id,
        "provider_id": provider_id,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return JwtSession(token=token, expires_at=expires_at)


def decode_jwt_token(token: str, verify_exp: bool = True) -> dict:
    settings = get_settings()
    options = {"verify_exp": verify_exp}
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options=options,
    )


def session_key(patient_id: str) -> str:
    return f"session:{patient_id}"


def store_session(redis_client, patient_id: str, token: str, ttl_seconds: int) -> None:
    payload = {"token": token}
    redis_client.setex(session_key(patient_id), ttl_seconds, json.dumps(payload))


def validate_session(redis_client, patient_id: str, token: str) -> bool:
    stored = redis_client.get(session_key(patient_id))
    if not stored:
        return False
    payload = json.loads(stored)
    return payload.get("token") == token


def clear_session(redis_client, patient_id: str) -> None:
    redis_client.delete(session_key(patient_id))
