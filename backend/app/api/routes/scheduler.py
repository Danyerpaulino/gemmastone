from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.scheduled_actions import DispatchActionsResponse, ScheduledActionOut
from app.services.scheduler import ScheduledActionDispatcher

router = APIRouter()


@router.post("/dispatch-actions", response_model=DispatchActionsResponse)
def dispatch_scheduled_actions(
    limit: int = 50,
    dry_run: bool = False,
    db: Session = Depends(get_db),
) -> DispatchActionsResponse:
    dispatcher = ScheduledActionDispatcher(db)
    actions = dispatcher.dispatch_due(limit=limit, dry_run=dry_run)
    return DispatchActionsResponse(
        dispatched=len(actions),
        items=[ScheduledActionOut.model_validate(action) for action in actions],
    )
