"""Refresh workflow outputs when new lab results arrive."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.crud import nudge as nudge_crud
from app.crud import prevention_plan as plan_crud
from app.db.models import NudgeCampaign, StoneAnalysis
from app.schemas.plan import NudgeCampaignCreate, NudgeCreate, PreventionPlanCreate, PreventionPlanUpdate
from app.workflows.kidney_stone import (
    education_generation_node,
    lab_integration_node,
    nudge_scheduling_node,
    prevention_planning_node,
    treatment_decision_node,
)


async def refresh_analysis_with_labs(
    db: Session,
    analysis: StoneAnalysis,
    crystallography_results: dict | None,
    urine_24hr_results: dict | None,
) -> dict[str, Any]:
    """Recompute treatment + prevention outputs based on new labs."""
    state: dict[str, Any] = {
        "patient_id": str(analysis.patient_id),
        "provider_id": str(analysis.provider_id),
        "ct_scan_path": analysis.ct_scan_path,
        "stones_detected": analysis.stones_detected or [],
        "predicted_composition": analysis.predicted_composition,
        "composition_confidence": analysis.composition_confidence or 0.0,
        "total_stone_burden_mm3": analysis.total_stone_burden_mm3,
        "hydronephrosis_level": analysis.hydronephrosis_level,
        "crystallography_results": crystallography_results,
        "urine_24hr_results": urine_24hr_results,
    }

    state = await lab_integration_node(state)
    state = await treatment_decision_node(state)
    state = await prevention_planning_node(state)
    state = await education_generation_node(state)
    state = await nudge_scheduling_node(state)

    analysis.predicted_composition = state.get("predicted_composition")
    analysis.composition_confidence = state.get("composition_confidence")
    analysis.treatment_recommendation = state.get("treatment_recommendation")
    analysis.treatment_rationale = state.get("treatment_rationale")
    analysis.urgency_level = state.get("urgency_level")
    analysis.provider_approved = False
    analysis.approved_at = None
    analysis.provider_notes = None
    analysis.workflow_state = _serialize_state(state)

    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    latest_plan = plan_crud.get_latest_plan(db, analysis.patient_id)
    plan_payload = PreventionPlanCreate(
        analysis_id=analysis.id,
        patient_id=analysis.patient_id,
        dietary_recommendations=state.get("dietary_recommendations"),
        fluid_intake_target_ml=state.get("fluid_intake_target_ml"),
        medications_recommended=state.get("medications_recommended"),
        lifestyle_modifications=state.get("lifestyle_modifications"),
        education_materials=state.get("education_materials"),
        personalized_summary=state.get("personalized_summary"),
        active=True,
    )
    new_plan = plan_crud.create_plan(db, plan_payload)

    if latest_plan and latest_plan.active and latest_plan.id != new_plan.id:
        plan_crud.update_plan(
            db,
            latest_plan,
            PreventionPlanUpdate(active=False, superseded_by=new_plan.id),
        )

    settings = get_settings()
    nudge_schedule = state.get("nudge_schedule", []) or []
    if settings.disable_scheduled_sms:
        nudge_schedule = [item for item in nudge_schedule if item.get("channel") != "sms"]

    campaign = None
    nudges: list = []
    if nudge_schedule:
        campaign = nudge_crud.create_campaign(
            db,
            NudgeCampaignCreate(
                patient_id=analysis.patient_id,
                plan_id=new_plan.id,
                status="pending_approval",
            ),
        )

        db.query(NudgeCampaign).filter(
            NudgeCampaign.patient_id == analysis.patient_id,
            NudgeCampaign.id != campaign.id,
        ).update({"status": "paused"}, synchronize_session=False)
        db.commit()

        nudge_payloads = []
        for nudge in nudge_schedule:
            nudge_payloads.append(
                NudgeCreate(
                    campaign_id=campaign.id,
                    patient_id=analysis.patient_id,
                    scheduled_time=nudge["time"],
                    channel=nudge["channel"],
                    template=nudge.get("template"),
                    message_content=nudge.get("message"),
                    status="pending_approval",
                )
            )

        nudges = nudge_crud.create_nudges(db, nudge_payloads) if nudge_payloads else []

    return {
        "analysis": analysis,
        "plan": new_plan,
        "campaign": campaign,
        "nudges": nudges,
        "state": state,
    }


def _serialize_state(value: Any) -> Any:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return {"_binary": True, "size_bytes": len(value)}
    if isinstance(value, dict):
        return {k: _serialize_state(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_state(v) for v in value]
    return value
