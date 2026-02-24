from datetime import date, datetime
import json
from pathlib import Path
import tempfile
import shutil
from uuid import UUID, uuid4
import zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.crud import analysis as analysis_crud
from app.crud import lab_result as lab_crud
from app.crud import nudge as nudge_crud
from app.crud import prevention_plan as plan_crud
from app.core.settings import get_settings
from app.db.models import Patient, Provider
from app.db.session import get_db
from app.schemas.analysis import StoneAnalysisCreate, StoneAnalysisPublic
from app.schemas.lab_result import LabResultCreate, LabResultOut, LabResultUpdate
from app.schemas.ct_analysis import (
    CTAnalysisResponse,
    CTAnalyzeUriRequest,
    CTSignedUploadRequest,
    CTSignedUploadResponse,
)
from app.schemas.plan import (
    NudgeCampaignCreate,
    NudgeCreate,
    NudgeCampaignOut,
    NudgeOut,
    PreventionPlanCreate,
    PreventionPlanOut,
)
from app.services.lab_validation import validate_lab_results
from app.services.storage import ObjectStorage
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

    storage = ObjectStorage()
    stored = storage.upload(file)

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

    return await _run_analysis(
        db=db,
        patient_id=patient_id,
        provider_id=provider_id,
        stored=stored,
        storage=storage,
        explicit_crystallography=explicit_crystallography,
        explicit_urine=explicit_urine,
        db_crystallography=db_crystallography,
        db_urine=db_urine,
        crystallography_record=crystallography_record,
        urine_record=urine_record,
    )


@router.post("/sign-upload", response_model=CTSignedUploadResponse)
async def sign_ct_upload(
    payload: CTSignedUploadRequest,
) -> CTSignedUploadResponse:
    storage = ObjectStorage(mode="gcs")
    try:
        signed = storage.sign_upload(
            filename=payload.filename,
            content_type=payload.content_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CTSignedUploadResponse(
        upload_url=signed.upload_url,
        gcs_uri=signed.gcs_uri,
        headers=signed.headers,
        expires_in=signed.expires_in,
    )


@router.post("/analyze-uri", response_model=CTAnalysisResponse)
async def analyze_ct_uri(
    payload: CTAnalyzeUriRequest,
    db: Session = Depends(get_db),
) -> CTAnalysisResponse:
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=400, detail="Patient does not exist")

    provider = db.query(Provider).filter(Provider.id == payload.provider_id).first()
    if not provider:
        raise HTTPException(status_code=400, detail="Provider does not exist")

    storage = ObjectStorage(mode="gcs")
    try:
        stored = storage.from_gcs_uri(payload.gcs_uri)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    explicit_crystallography = payload.crystallography_results
    explicit_urine = payload.urine_24hr_results
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
            db, payload.patient_id, result_type="crystallography"
        )
        if crystallography_record:
            db_crystallography = crystallography_record.results
    if explicit_urine is None:
        urine_record = lab_crud.get_latest_lab_result(
            db, payload.patient_id, result_type="urine_24hr"
        )
        if urine_record:
            db_urine = urine_record.results

    return await _run_analysis(
        db=db,
        patient_id=payload.patient_id,
        provider_id=payload.provider_id,
        stored=stored,
        storage=storage,
        explicit_crystallography=explicit_crystallography,
        explicit_urine=explicit_urine,
        db_crystallography=db_crystallography,
        db_urine=db_urine,
        crystallography_record=crystallography_record,
        urine_record=urine_record,
    )


def _serialize_state(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        # Avoid storing large binaries in workflow_state; keep a lightweight marker instead.
        return {"_binary": True, "size_bytes": len(value)}
    if isinstance(value, dict):
        return {k: _serialize_state(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_state(v) for v in value]
    return value


async def _run_analysis(
    *,
    db: Session,
    patient_id: UUID,
    provider_id: UUID,
    stored,
    storage: ObjectStorage,
    explicit_crystallography: dict | None,
    explicit_urine: dict | None,
    db_crystallography: dict | None,
    db_urine: dict | None,
    crystallography_record,
    urine_record,
) -> CTAnalysisResponse:
    workflow = build_workflow()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        local_file = storage.download_to_path(stored, tmp_path / stored.filename)
        ct_path = _prepare_ct_payload(local_file, tmp_path)

        initial_state = {
            "patient_id": str(patient_id),
            "provider_id": str(provider_id),
            "ct_scan_path": stored.uri,
            "ct_scan_local_path": str(ct_path),
            "crystallography_results": (
                explicit_crystallography
                if explicit_crystallography is not None
                else db_crystallography
            ),
            "urine_24hr_results": explicit_urine if explicit_urine is not None else db_urine,
        }

        try:
            state = await workflow.ainvoke(initial_state)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Workflow failed: {exc}") from exc

    state_for_storage = dict(state)
    state_for_storage.pop("ct_scan_local_path", None)

    analysis_payload = StoneAnalysisCreate(
        patient_id=patient_id,
        provider_id=provider_id,
        ct_scan_path=stored.uri,
        ct_scan_date=date.today(),
        stones_detected=state.get("stones_detected", []),
        predicted_composition=state.get("predicted_composition"),
        composition_confidence=state.get("composition_confidence"),
        stone_3d_model=state.get("stone_3d_model"),
        total_stone_burden_mm3=state.get("total_stone_burden_mm3"),
        hydronephrosis_level=state.get("hydronephrosis_level"),
        treatment_recommendation=state.get("treatment_recommendation"),
        treatment_rationale=state.get("treatment_rationale"),
        urgency_level=state.get("urgency_level"),
        workflow_state=_serialize_state(state_for_storage),
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
    nudge_schedule = state.get("nudge_schedule") or []
    settings = get_settings()
    if settings.disable_scheduled_sms:
        nudge_schedule = [item for item in nudge_schedule if item.get("channel") != "sms"]

    if plan and nudge_schedule:
        campaign_payload = NudgeCampaignCreate(
            patient_id=patient_id,
            plan_id=plan.id,
            status="pending_approval",
        )
        campaign = nudge_crud.create_campaign(db, campaign_payload)
        nudge_payloads = []
        for nudge in nudge_schedule:
            nudge_payloads.append(
                NudgeCreate(
                    campaign_id=campaign.id,
                    patient_id=patient_id,
                    scheduled_time=nudge["time"],
                    channel=nudge["channel"],
                    template=nudge.get("template"),
                    message_content=nudge.get("message"),
                    status="pending_approval",
                )
            )
        nudges = nudge_crud.create_nudges(db, nudge_payloads)

    labs = lab_crud.list_lab_results(db, analysis_id=analysis.id, limit=500)
    analysis_out = StoneAnalysisPublic.model_validate(analysis).model_copy(
        update={"lab_results": [LabResultOut.model_validate(lab) for lab in labs]}
    )

    return CTAnalysisResponse(
        analysis=analysis_out,
        prevention_plan=PreventionPlanOut.model_validate(plan) if plan else None,
        nudge_campaign=NudgeCampaignOut.model_validate(campaign) if campaign else None,
        nudges=[NudgeOut.model_validate(n) for n in nudges] if nudges else [],
        workflow_state=_serialize_state(state_for_storage),
    )


def _prepare_ct_payload(upload_path: Path, workspace: Path) -> Path:
    if zipfile.is_zipfile(upload_path):
        extract_dir = workspace / uuid4().hex
        extract_dir.mkdir(parents=True, exist_ok=True)
        _safe_extract_zip(upload_path, extract_dir)
        return extract_dir
    return upload_path


def _safe_extract_zip(zip_path: Path, target_dir: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            member_path = target_dir / member.filename
            if not _is_within_directory(target_dir, member_path):
                raise HTTPException(status_code=400, detail="Invalid ZIP contents.")
            member_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as src, member_path.open("wb") as dest:
                shutil.copyfileobj(src, dest)


def _is_within_directory(base_dir: Path, target: Path) -> bool:
    try:
        base = base_dir.resolve()
        return base in target.resolve().parents or target.resolve() == base
    except FileNotFoundError:
        return False


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
