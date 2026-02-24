from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.api.deps import get_current_patient
from app.crud import patient as patient_crud
from app.db.session import get_db
from app.schemas.auth import OtpRequest, OtpRequestResponse, OtpVerify, OtpVerifyResponse
from app.schemas.patient import PatientOut
from app.services.auth import (
    OtpRateLimitError,
    OtpVerificationError,
    clear_session,
    create_jwt_session,
    decode_jwt_token,
    normalize_phone,
    request_otp,
    verify_otp,
    store_session,
    validate_session,
)
from app.services.context_builder import enqueue_context_rebuild
from app.services.scheduler import create_default_schedule
from app.services.telnyx_client import TelnyxClient
from app.services.redis_client import get_redis

router = APIRouter()


def _set_session_cookie(response: JSONResponse, token: str, expires_at: datetime) -> None:
    settings = get_settings()
    max_age = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    response.set_cookie(
        key=settings.jwt_cookie_name,
        value=token,
        httponly=True,
        secure=settings.jwt_cookie_secure,
        samesite="lax",
        max_age=max_age,
    )


@router.post("/request-otp", response_model=OtpRequestResponse)
def request_otp_code(
    payload: OtpRequest,
    db: Session = Depends(get_db),
) -> OtpRequestResponse:
    settings = get_settings()
    redis_client = get_redis()
    normalized = normalize_phone(payload.phone)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number.")

    patient = patient_crud.get_patient_by_phone(db, normalized)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    try:
        normalized, code = request_otp(redis_client, normalized)
    except OtpRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    message = f"Klen AI: Your verification code is {code}. It expires in 5 minutes."
    TelnyxClient().send_sms(normalized, message)

    response = OtpRequestResponse(status="sent")
    if settings.messaging_mode == "mock" and settings.env != "prod":
        response.debug_code = code
    return response


@router.post("/verify-otp", response_model=OtpVerifyResponse)
def verify_otp_code(
    payload: OtpVerify,
    db: Session = Depends(get_db),
) -> JSONResponse:
    settings = get_settings()
    redis_client = get_redis()
    normalized = normalize_phone(payload.phone)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number.")

    try:
        normalized = verify_otp(redis_client, normalized, payload.code)
    except OtpVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    patient = patient_crud.get_patient_by_phone(db, normalized)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    was_onboarded = patient.onboarding_completed
    updates = {"phone_verified": True, "phone": normalized}
    if not patient.onboarding_completed:
        updates["onboarding_completed"] = True
        prefs = dict(patient.contact_preferences or {})
        prefs.setdefault("sms", True)
        prefs.setdefault("email", True)
        prefs["voice"] = True
        updates["contact_preferences"] = prefs
    patient_crud.update_patient(db, patient, updates)

    if not was_onboarded:
        enqueue_context_rebuild(
            patient.id,
            "signup",
            {"source": patient.onboarding_source or "otp"},
        )
        create_default_schedule(db, patient)

    session = create_jwt_session(str(patient.id), str(patient.provider_id) if patient.provider_id else None)
    ttl_seconds = settings.jwt_expiry_days * 24 * 60 * 60
    store_session(redis_client, str(patient.id), session.token, ttl_seconds)

    payload_out = OtpVerifyResponse(
        patient_id=patient.id,
        provider_id=patient.provider_id,
        expires_at=session.expires_at,
    )
    response = JSONResponse(payload_out.model_dump(mode="json"))
    _set_session_cookie(response, session.token, session.expires_at)
    return response


@router.post("/refresh", response_model=OtpVerifyResponse)
def refresh_session(request: Request) -> JSONResponse:
    settings = get_settings()
    token = request.cookies.get(settings.jwt_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing session cookie.")

    try:
        payload = decode_jwt_token(token, verify_exp=False)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session.")

    patient_id = payload.get("sub")
    provider_id = payload.get("provider_id")
    if not patient_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session.")

    redis_client = get_redis()
    if not validate_session(redis_client, patient_id, token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.")

    session = create_jwt_session(patient_id, provider_id)
    ttl_seconds = settings.jwt_expiry_days * 24 * 60 * 60
    store_session(redis_client, patient_id, session.token, ttl_seconds)

    payload_out = OtpVerifyResponse(
        patient_id=patient_id,
        provider_id=provider_id,
        expires_at=session.expires_at,
    )
    response = JSONResponse(payload_out.model_dump(mode="json"))
    _set_session_cookie(response, session.token, session.expires_at)
    return response


@router.post("/logout")
def logout(request: Request) -> JSONResponse:
    settings = get_settings()
    token = request.cookies.get(settings.jwt_cookie_name)
    if token:
        try:
            payload = decode_jwt_token(token, verify_exp=False)
            patient_id = payload.get("sub")
            if patient_id:
                clear_session(get_redis(), patient_id)
        except Exception:
            pass

    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie(settings.jwt_cookie_name)
    return response


@router.get("/me", response_model=PatientOut)
def get_me(current_patient=Depends(get_current_patient)) -> PatientOut:
    return PatientOut.model_validate(current_patient)
