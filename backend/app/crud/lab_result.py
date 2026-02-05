from sqlalchemy.orm import Session

from app.db.models import LabResult
from app.schemas.lab_result import LabResultCreate, LabResultUpdate


def create_lab_result(db: Session, payload: LabResultCreate) -> LabResult:
    item = LabResult(**payload.model_dump(exclude_unset=True))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_lab_result(db: Session, lab_id) -> LabResult | None:
    return db.query(LabResult).filter(LabResult.id == lab_id).first()


def list_lab_results(
    db: Session,
    offset: int = 0,
    limit: int = 100,
    patient_id=None,
    analysis_id=None,
    result_type: str | None = None,
) -> list[LabResult]:
    query = db.query(LabResult)
    if patient_id is not None:
        query = query.filter(LabResult.patient_id == patient_id)
    if analysis_id is not None:
        query = query.filter(LabResult.analysis_id == analysis_id)
    if result_type:
        query = query.filter(LabResult.result_type == result_type)
    return query.order_by(LabResult.result_date.desc().nullslast(), LabResult.created_at.desc()).offset(
        offset
    ).limit(limit).all()


def count_lab_results(
    db: Session,
    patient_id=None,
    analysis_id=None,
    result_type: str | None = None,
) -> int:
    query = db.query(LabResult)
    if patient_id is not None:
        query = query.filter(LabResult.patient_id == patient_id)
    if analysis_id is not None:
        query = query.filter(LabResult.analysis_id == analysis_id)
    if result_type:
        query = query.filter(LabResult.result_type == result_type)
    return query.count()


def get_latest_lab_result(
    db: Session,
    patient_id,
    result_type: str | None = None,
) -> LabResult | None:
    query = db.query(LabResult).filter(LabResult.patient_id == patient_id)
    if result_type:
        query = query.filter(LabResult.result_type == result_type)
    return query.order_by(LabResult.result_date.desc().nullslast(), LabResult.created_at.desc()).first()


def update_lab_result(db: Session, lab: LabResult, payload: LabResultUpdate) -> LabResult:
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(lab, key, value)
    db.add(lab)
    db.commit()
    db.refresh(lab)
    return lab


def delete_lab_result(db: Session, lab: LabResult) -> None:
    db.delete(lab)
    db.commit()
