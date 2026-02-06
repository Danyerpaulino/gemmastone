from sqlalchemy.orm import Session

from app.db.models import StoneAnalysis
from app.schemas.analysis import StoneAnalysisCreate


def create_analysis(db: Session, payload: StoneAnalysisCreate) -> StoneAnalysis:
    analysis = StoneAnalysis(**payload.model_dump(exclude_unset=True))
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


def get_analysis(db: Session, analysis_id) -> StoneAnalysis | None:
    return db.query(StoneAnalysis).filter(StoneAnalysis.id == analysis_id).first()


def list_analyses(
    db: Session,
    offset: int = 0,
    limit: int = 100,
    patient_id=None,
) -> list[StoneAnalysis]:
    query = db.query(StoneAnalysis)
    if patient_id is not None:
        query = query.filter(StoneAnalysis.patient_id == patient_id)
    return (
        query.order_by(StoneAnalysis.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_analyses(db: Session, patient_id=None) -> int:
    query = db.query(StoneAnalysis)
    if patient_id is not None:
        query = query.filter(StoneAnalysis.patient_id == patient_id)
    return query.count()
