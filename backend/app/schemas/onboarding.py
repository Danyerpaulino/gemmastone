from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProviderReferralOut(BaseModel):
    id: UUID
    name: str
    practice_name: str | None = None
    referral_code: str
    qr_code_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class OnboardingRequest(BaseModel):
    first_name: str
    last_name: str
    phone: str
    email: str | None = None


class OnboardingResponse(BaseModel):
    patient_id: UUID
    provider_id: UUID
    phone: str
    debug_code: str | None = None
