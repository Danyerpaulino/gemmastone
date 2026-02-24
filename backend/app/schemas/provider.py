from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProviderBase(BaseModel):
    email: str
    name: str
    npi: str | None = None
    specialty: str | None = None
    practice_name: str | None = None


class ProviderCreate(ProviderBase):
    pass


class ProviderOut(ProviderBase):
    id: UUID
    referral_code: str | None = None
    qr_code_url: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ProviderList(BaseModel):
    items: list[ProviderOut]
    total: int
