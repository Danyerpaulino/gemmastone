from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScheduledActionOut(BaseModel):
    id: UUID
    patient_id: UUID
    action_type: str
    scheduled_for: datetime
    recurrence: str | None = None
    payload: dict[str, Any] | None = None
    status: str | None = None
    executed_at: datetime | None = None
    result: dict[str, Any] | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DispatchActionsResponse(BaseModel):
    dispatched: int
    items: list[ScheduledActionOut]
