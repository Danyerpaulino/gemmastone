from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OtpRequest(BaseModel):
    phone: str


class OtpVerify(BaseModel):
    phone: str
    code: str


class OtpRequestResponse(BaseModel):
    status: str
    debug_code: str | None = None


class OtpVerifyResponse(BaseModel):
    patient_id: UUID
    provider_id: UUID | None = None
    expires_at: datetime
