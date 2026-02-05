from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.crud import analysis as analysis_crud
from app.crud import prevention_plan as plan_crud
from app.db.session import get_db
from app.schemas.plan import PlanApproval, PreventionPlanCreate, PreventionPlanOut, PreventionPlanUpdate

router = APIRouter()


@router.post("/{plan_id}/approve", response_model=PreventionPlanOut)
def approve_plan(
    plan_id: UUID,
    payload: PlanApproval,
    db: Session = Depends(get_db),
) -> PreventionPlanOut:
    plan = plan_crud.get_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    analysis = analysis_crud.get_analysis(db, plan.analysis_id)
    if analysis:
        analysis.provider_approved = True
        analysis.approved_at = datetime.utcnow()
        analysis.provider_notes = payload.provider_notes
        db.add(analysis)

    updated_plan = plan
    if payload.modifications:
        base_data = PreventionPlanCreate(
            analysis_id=plan.analysis_id,
            patient_id=plan.patient_id,
            dietary_recommendations=plan.dietary_recommendations,
            fluid_intake_target_ml=plan.fluid_intake_target_ml,
            medications_recommended=plan.medications_recommended,
            lifestyle_modifications=plan.lifestyle_modifications,
            education_materials=plan.education_materials,
            personalized_summary=plan.personalized_summary,
            active=True,
        )
        modifications = payload.modifications.model_dump(exclude_unset=True)
        base_dict = base_data.model_dump(exclude_unset=True)
        base_dict.update({k: v for k, v in modifications.items() if v is not None})
        updated_plan = plan_crud.create_plan(db, PreventionPlanCreate(**base_dict))

        plan_crud.update_plan(
            db,
            plan,
            PreventionPlanUpdate(active=False, superseded_by=updated_plan.id),
        )

    db.commit()

    return PreventionPlanOut.model_validate(updated_plan)
