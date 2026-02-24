from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.db.models import ContextBuild, PatientContext
from app.db.session import get_db
from app.schemas.context import (
    ContextBuildList,
    ContextBuildOut,
    ContextRebuildRequest,
    PatientContextOut,
)
from app.services.context_builder import ContextBuilder

router = APIRouter()


@router.post("/rebuild/{patient_id}", response_model=PatientContextOut)
async def rebuild_context(
    patient_id: UUID,
    payload: ContextRebuildRequest | None = None,
    db: Session = Depends(get_db),
) -> PatientContextOut:
    trigger = payload.trigger if payload and payload.trigger else "manual"
    event_data = payload.event_data if payload else None
    builder = ContextBuilder(db)
    try:
        context = await builder.build_context(patient_id, trigger, event_data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PatientContextOut.model_validate(context)


@router.get("/{patient_id}", response_model=PatientContextOut)
def get_context(
    patient_id: UUID,
    db: Session = Depends(get_db),
) -> PatientContextOut:
    ctx = (
        db.query(PatientContext)
        .filter(PatientContext.patient_id == patient_id)
        .first()
    )
    if not ctx:
        raise HTTPException(status_code=404, detail="Context not found")
    return PatientContextOut.model_validate(ctx)


@router.get("/history/{patient_id}", response_model=ContextBuildList)
def get_context_history(
    patient_id: UUID,
    db: Session = Depends(get_db),
) -> ContextBuildList:
    builds = (
        db.query(ContextBuild)
        .filter(ContextBuild.patient_id == patient_id)
        .order_by(ContextBuild.created_at.desc())
        .all()
    )
    return ContextBuildList(
        items=[ContextBuildOut.model_validate(build) for build in builds],
        total=len(builds),
    )
