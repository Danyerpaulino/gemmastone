from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.crud import patient as patient_crud
from app.crud import provider as provider_crud
from app.db.models import Patient
from app.db.session import get_db
from app.schemas.onboarding import OnboardingRequest, OnboardingResponse, ProviderReferralOut
from app.services.auth import OtpRateLimitError, normalize_phone, request_otp
from app.services.telnyx_client import TelnyxClient
from app.services.redis_client import get_redis

router = APIRouter()


@router.get("/provider/{referral_code}", response_model=ProviderReferralOut)
def get_provider_by_referral(
    referral_code: str,
    db: Session = Depends(get_db),
) -> ProviderReferralOut:
    provider = provider_crud.get_provider_by_referral_code(db, referral_code.lower())
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral code not found.")
    return ProviderReferralOut.model_validate(provider)


@router.post("/join/{referral_code}", response_model=OnboardingResponse)
def join_with_referral(
    referral_code: str,
    payload: OnboardingRequest,
    db: Session = Depends(get_db),
) -> OnboardingResponse:
    settings = get_settings()
    referral_code = referral_code.lower()
    provider = provider_crud.get_provider_by_referral_code(db, referral_code)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral code not found.")

    normalized = normalize_phone(payload.phone)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number.")

    existing = patient_crud.get_patient_by_phone(db, normalized)
    onboarding_source = f"qr:{referral_code}"
    if existing:
        if existing.provider_id and existing.provider_id != provider.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already registered with another provider.",
            )
        updates = {
            "provider_id": provider.id,
            "first_name": payload.first_name,
            "last_name": payload.last_name,
            "phone": normalized,
            "onboarding_source": onboarding_source,
        }
        if payload.email is not None:
            updates["email"] = payload.email
        patient = patient_crud.update_patient(db, existing, updates)
    else:
        patient = Patient(
            provider_id=provider.id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=normalized,
            onboarding_source=onboarding_source,
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)

    redis_client = get_redis()
    try:
        _, code = request_otp(redis_client, normalized)
    except OtpRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    message = f"Klen AI: Your verification code is {code}. It expires in 5 minutes."
    TelnyxClient().send_sms(normalized, message)

    response = OnboardingResponse(
        patient_id=patient.id,
        provider_id=provider.id,
        phone=normalized,
    )
    if settings.messaging_mode == "mock" and settings.env != "prod":
        response.debug_code = code
    return response
