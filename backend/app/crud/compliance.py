from sqlalchemy.orm import Session

from app.db.models import ComplianceLog


def list_compliance_logs(
    db: Session,
    patient_id,
    offset: int = 0,
    limit: int = 100,
) -> list[ComplianceLog]:
    return (
        db.query(ComplianceLog)
        .filter(ComplianceLog.patient_id == patient_id)
        .order_by(ComplianceLog.log_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_compliance_logs(db: Session, patient_id) -> int:
    return (
        db.query(ComplianceLog)
        .filter(ComplianceLog.patient_id == patient_id)
        .count()
    )
