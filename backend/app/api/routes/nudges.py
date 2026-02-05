from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.plan import NudgeOut
from app.services.nudge_dispatcher import NudgeDispatcher

router = APIRouter()


class NudgeDispatchResponse(BaseModel):
    dispatched: int
    items: list[NudgeOut]


@router.post("/dispatch", response_model=NudgeDispatchResponse)
def dispatch_due_nudges(
    limit: int = 50,
    dry_run: bool = False,
    db: Session = Depends(get_db),
) -> NudgeDispatchResponse:
    dispatcher = NudgeDispatcher(db)
    nudges = dispatcher.dispatch_due(limit=limit, dry_run=dry_run)
    return NudgeDispatchResponse(
        dispatched=len(nudges),
        items=[NudgeOut.model_validate(n) for n in nudges],
    )
