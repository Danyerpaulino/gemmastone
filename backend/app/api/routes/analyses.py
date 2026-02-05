from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.crud import analysis as analysis_crud
from app.crud import lab_result as lab_crud
from app.db.models import Patient, Provider
from app.db.session import get_db
from app.schemas.analysis import StoneAnalysisCreate, StoneAnalysisList, StoneAnalysisOut
from app.schemas.lab_result import LabResultOut

router = APIRouter()


@router.post("/", response_model=StoneAnalysisOut, status_code=201)
def create_analysis(
    payload: StoneAnalysisCreate,
    db: Session = Depends(get_db),
) -> StoneAnalysisOut:
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=400, detail="Patient does not exist")

    provider = db.query(Provider).filter(Provider.id == payload.provider_id).first()
    if not provider:
        raise HTTPException(status_code=400, detail="Provider does not exist")

    return analysis_crud.create_analysis(db, payload)


@router.get("/", response_model=StoneAnalysisList)
def list_analyses(
    offset: int = 0,
    limit: int = 100,
    patient_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> StoneAnalysisList:
    items = analysis_crud.list_analyses(db, offset=offset, limit=limit, patient_id=patient_id)
    total = analysis_crud.count_analyses(db, patient_id=patient_id)
    return StoneAnalysisList(items=items, total=total)


@router.get("/{analysis_id}", response_model=StoneAnalysisOut)
def get_analysis(
    analysis_id: UUID,
    db: Session = Depends(get_db),
) -> StoneAnalysisOut:
    analysis = analysis_crud.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    labs = lab_crud.list_lab_results(db, analysis_id=analysis_id, limit=500)
    analysis_out = StoneAnalysisOut.model_validate(analysis).model_copy(
        update={"lab_results": [LabResultOut.model_validate(lab) for lab in labs]}
    )
    return analysis_out
