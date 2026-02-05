from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.crud import lab_result as lab_crud
from app.db.models import Patient, StoneAnalysis
from app.db.session import get_db
from app.schemas.lab_result import (
    LabResultCreate,
    LabResultList,
    LabResultOut,
    LabResultUpdate,
)
from app.services.lab_validation import validate_lab_results

router = APIRouter()


@router.post("/", response_model=LabResultOut, status_code=201)
def create_lab_result(
    payload: LabResultCreate,
    db: Session = Depends(get_db),
) -> LabResultOut:
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=400, detail="Patient does not exist")
    if payload.analysis_id:
        analysis = db.query(StoneAnalysis).filter(StoneAnalysis.id == payload.analysis_id).first()
        if not analysis:
            raise HTTPException(status_code=400, detail="Analysis does not exist")
    _validate_lab_payload(payload.result_type, payload.results)
    return lab_crud.create_lab_result(db, payload)


@router.get("/", response_model=LabResultList)
def list_lab_results(
    offset: int = 0,
    limit: int = 100,
    patient_id: UUID | None = None,
    analysis_id: UUID | None = None,
    result_type: str | None = None,
    db: Session = Depends(get_db),
) -> LabResultList:
    items = lab_crud.list_lab_results(
        db,
        offset=offset,
        limit=limit,
        patient_id=patient_id,
        analysis_id=analysis_id,
        result_type=result_type,
    )
    total = lab_crud.count_lab_results(
        db,
        patient_id=patient_id,
        analysis_id=analysis_id,
        result_type=result_type,
    )
    return LabResultList(items=items, total=total)


@router.get("/{lab_id}", response_model=LabResultOut)
def get_lab_result(
    lab_id: UUID,
    db: Session = Depends(get_db),
) -> LabResultOut:
    lab = lab_crud.get_lab_result(db, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab result not found")
    return lab


@router.patch("/{lab_id}", response_model=LabResultOut)
def update_lab_result(
    lab_id: UUID,
    payload: LabResultUpdate,
    db: Session = Depends(get_db),
) -> LabResultOut:
    lab = lab_crud.get_lab_result(db, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab result not found")
    if payload.analysis_id:
        analysis = db.query(StoneAnalysis).filter(StoneAnalysis.id == payload.analysis_id).first()
        if not analysis:
            raise HTTPException(status_code=400, detail="Analysis does not exist")
    if payload.results is not None:
        result_type = payload.result_type or lab.result_type
        _validate_lab_payload(result_type, payload.results)
    return lab_crud.update_lab_result(db, lab, payload)


@router.delete("/{lab_id}", status_code=204)
def delete_lab_result(
    lab_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    lab = lab_crud.get_lab_result(db, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab result not found")
    lab_crud.delete_lab_result(db, lab)
    return None


def _validate_lab_payload(result_type: str, results: dict) -> None:
    try:
        validate_lab_results(result_type, results)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
