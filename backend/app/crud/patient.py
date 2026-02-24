from sqlalchemy import func
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


def get_patient_by_phone(db: Session, phone: str) -> Patient | None:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if not digits:
        return db.query(Patient).filter(Patient.phone == phone).first()
    return (
        db.query(Patient)
        .filter(func.regexp_replace(Patient.phone, r"[^0-9]", "", "g") == digits)
        .first()
    )


def list_patients(db: Session, offset: int = 0, limit: int = 100) -> list[Patient]:
    return (
        db.query(Patient)
        .order_by(Patient.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_patients(db: Session) -> int:
    return db.query(Patient).count()


def update_patient(db: Session, patient: Patient, updates: dict) -> Patient:
    for key, value in updates.items():
        setattr(patient, key, value)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient
