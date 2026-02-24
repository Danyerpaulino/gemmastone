from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SmsMessageOut(BaseModel):
    id: UUID
    patient_id: UUID
    telnyx_message_id: str | None = None
    direction: str
    message_type: str | None = None
    content: str | None = None
    media_urls: list[str] | None = None
    status: str | None = None
    ai_response: str | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SmsMessageList(BaseModel):
    items: list[SmsMessageOut]
    total: int
