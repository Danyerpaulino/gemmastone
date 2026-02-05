from sqlalchemy.orm import Session

from app.db.models import PatientInteraction


def create_interaction(db: Session, interaction: PatientInteraction) -> PatientInteraction:
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return interaction


def list_interactions(
    db: Session,
    patient_id,
    offset: int = 0,
    limit: int = 100,
) -> list[PatientInteraction]:
    return (
        db.query(PatientInteraction)
        .filter(PatientInteraction.patient_id == patient_id)
        .order_by(PatientInteraction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
