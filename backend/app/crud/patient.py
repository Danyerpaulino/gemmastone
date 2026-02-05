from sqlalchemy.orm import Session

from app.db.models import Patient
from app.schemas.patient import PatientCreate


def create_patient(db: Session, payload: PatientCreate) -> Patient:
    patient = Patient(**payload.model_dump(exclude_unset=True))
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def get_patient(db: Session, patient_id) -> Patient | None:
    return db.query(Patient).filter(Patient.id == patient_id).first()


def list_patients(db: Session, offset: int = 0, limit: int = 100) -> list[Patient]:
    return db.query(Patient).offset(offset).limit(limit).all()


def count_patients(db: Session) -> int:
    return db.query(Patient).count()
