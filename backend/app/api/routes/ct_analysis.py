from datetime import date, datetime
import json
from pathlib import Path
from uuid import UUID, uuid4
import zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.crud import analysis as analysis_crud
from app.crud import lab_result as lab_crud
from app.crud import nudge as nudge_crud
from app.crud import prevention_plan as plan_crud
from app.db.models import Patient, Provider
from app.db.session import get_db
from app.schemas.analysis import StoneAnalysisCreate, StoneAnalysisOut
from app.schemas.lab_result import LabResultCreate, LabResultOut, LabResultUpdate
from app.schemas.ct_analysis import CTAnalysisResponse
from app.schemas.plan import (
    NudgeCampaignCreate,
    NudgeCreate,
    NudgeCampaignOut,
    NudgeOut,
    PreventionPlanCreate,
    PreventionPlanOut,
)
from app.services.lab_validation import validate_lab_results
from app.workflows.kidney_stone import build_workflow

router = APIRouter()


@router.post("/analyze", response_model=CTAnalysisResponse)
async def analyze_ct(
    file: UploadFile = File(...),
    patient_id: UUID = Form(...),
    provider_id: UUID = Form(...),
    crystallography_results: str | None = Form(None),
    urine_24hr_results: str | None = Form(None),
    db: Session = Depends(get_db),
) -> CTAnalysisResponse:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=400, detail="Patient does not exist")

    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=400, detail="Provider does not exist")

    upload_root = Path(__file__).resolve().parents[3] / "data" / "ct_scans"
    upload_root.mkdir(parents=True, exist_ok=True)
    scan_dir = upload_root / uuid4().hex
    scan_dir.mkdir(parents=True, exist_ok=True)

    filename = file.filename or "ct_scan"
    saved_path = scan_dir / filename
    contents = await file.read()
    saved_path.write_bytes(contents)

    if filename.lower().endswith(".zip"):
        with zipfile.ZipFile(saved_path, "r") as archive:
            archive.extractall(scan_dir)

    explicit_crystallography = _parse_json_field(
        crystallography_results, "crystallography_results"
    )
    explicit_urine = _parse_json_field(urine_24hr_results, "urine_24hr_results")
    if explicit_crystallography is not None:
        _validate_lab_payload("crystallography", explicit_crystallography)
    if explicit_urine is not None:
        _validate_lab_payload("urine_24hr", explicit_urine)

    db_crystallography = None
    db_urine = None
    crystallography_record = None
    urine_record = None
    if explicit_crystallography is None:
        crystallography_record = lab_crud.get_latest_lab_result(
            db, patient_id, result_type="crystallography"
        )
        if crystallography_record:
            db_crystallography = crystallography_record.results
    if explicit_urine is None:
        urine_record = lab_crud.get_latest_lab_result(db, patient_id, result_type="urine_24hr")
        if urine_record:
            db_urine = urine_record.results

    initial_state = {
        "patient_id": str(patient_id),
        "provider_id": str(provider_id),
        "ct_scan_path": str(scan_dir),
        "crystallography_results": (
            explicit_crystallography if explicit_crystallography is not None else db_crystallography
        ),
        "urine_24hr_results": explicit_urine if explicit_urine is not None else db_urine,
    }

    workflow = build_workflow()
    try:
        state = await workflow.ainvoke(initial_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workflow failed: {exc}") from exc

    analysis_payload = StoneAnalysisCreate(
        patient_id=patient_id,
        provider_id=provider_id,
        ct_scan_path=str(scan_dir),
        ct_scan_date=date.today(),
        stones_detected=state.get("stones_detected", []),
        predicted_composition=state.get("predicted_composition"),
        composition_confidence=state.get("composition_confidence"),
        treatment_recommendation=state.get("treatment_recommendation"),
        treatment_rationale=state.get("treatment_rationale"),
        urgency_level=state.get("urgency_level"),
        workflow_state=_serialize_state(state),
    )
    analysis = analysis_crud.create_analysis(db, analysis_payload)

    if explicit_crystallography is not None:
        lab_crud.create_lab_result(
            db,
            LabResultCreate(
                patient_id=patient_id,
                analysis_id=analysis.id,
                result_type="crystallography",
                result_date=date.today(),
                results=explicit_crystallography,
            ),
        )
    elif crystallography_record and crystallography_record.analysis_id is None:
        lab_crud.update_lab_result(
            db,
            crystallography_record,
            LabResultUpdate(analysis_id=analysis.id),
        )

    if explicit_urine is not None:
        lab_crud.create_lab_result(
            db,
            LabResultCreate(
                patient_id=patient_id,
                analysis_id=analysis.id,
                result_type="urine_24hr",
                result_date=date.today(),
                results=explicit_urine,
            ),
        )
    elif urine_record and urine_record.analysis_id is None:
        lab_crud.update_lab_result(
            db,
            urine_record,
            LabResultUpdate(analysis_id=analysis.id),
        )

    plan = None
    if state.get("dietary_recommendations") or state.get("fluid_intake_target_ml"):
        plan_payload = PreventionPlanCreate(
            analysis_id=analysis.id,
            patient_id=patient_id,
            dietary_recommendations=state.get("dietary_recommendations"),
            fluid_intake_target_ml=state.get("fluid_intake_target_ml"),
            medications_recommended=state.get("medications_recommended"),
            lifestyle_modifications=state.get("lifestyle_modifications"),
            education_materials=state.get("education_materials"),
            personalized_summary=state.get("personalized_summary"),
        )
        plan = plan_crud.create_plan(db, plan_payload)

    campaign = None
    nudges: list = []
    if plan and state.get("nudge_schedule"):
        campaign_payload = NudgeCampaignCreate(patient_id=patient_id, plan_id=plan.id)
        campaign = nudge_crud.create_campaign(db, campaign_payload)
        nudge_payloads = []
        for nudge in state.get("nudge_schedule", []):
            nudge_payloads.append(
                NudgeCreate(
                    campaign_id=campaign.id,
                    patient_id=patient_id,
                    scheduled_time=nudge["time"],
                    channel=nudge["channel"],
                    template=nudge.get("template"),
                    message_content=nudge.get("message"),
                    status="scheduled",
                )
            )
        nudges = nudge_crud.create_nudges(db, nudge_payloads)

    labs = lab_crud.list_lab_results(db, analysis_id=analysis.id, limit=500)
    analysis_out = StoneAnalysisOut.model_validate(analysis).model_copy(
        update={"lab_results": [LabResultOut.model_validate(lab) for lab in labs]}
    )

    return CTAnalysisResponse(
        analysis=analysis_out,
        prevention_plan=PreventionPlanOut.model_validate(plan) if plan else None,
        nudge_campaign=NudgeCampaignOut.model_validate(campaign) if campaign else None,
        nudges=[NudgeOut.model_validate(n) for n in nudges] if nudges else [],
        workflow_state=_serialize_state(state),
    )


def _serialize_state(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize_state(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_state(v) for v in value]
    return value


def _parse_json_field(raw_value: str | None, label: str) -> dict | None:
    if raw_value is None:
        return None
    raw_value = raw_value.strip()
    if not raw_value:
        return None
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON for {label}: {exc}",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail=f"{label} must be a JSON object")
    return parsed


def _validate_lab_payload(result_type: str, results: dict) -> None:
    try:
        validate_lab_results(result_type, results)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
