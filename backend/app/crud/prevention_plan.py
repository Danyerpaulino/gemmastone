from sqlalchemy.orm import Session

from app.db.models import PreventionPlan
from app.schemas.plan import PreventionPlanCreate, PreventionPlanUpdate


def create_plan(db: Session, payload: PreventionPlanCreate) -> PreventionPlan:
    plan = PreventionPlan(**payload.model_dump(exclude_unset=True))
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def get_plan(db: Session, plan_id) -> PreventionPlan | None:
    return db.query(PreventionPlan).filter(PreventionPlan.id == plan_id).first()


def get_latest_plan(db: Session, patient_id) -> PreventionPlan | None:
    return (
        db.query(PreventionPlan)
        .filter(PreventionPlan.patient_id == patient_id)
        .order_by(PreventionPlan.created_at.desc())
        .first()
    )


def list_plans(
    db: Session,
    patient_id=None,
    offset: int = 0,
    limit: int = 100,
) -> list[PreventionPlan]:
    query = db.query(PreventionPlan)
    if patient_id is not None:
        query = query.filter(PreventionPlan.patient_id == patient_id)
    return query.order_by(PreventionPlan.created_at.desc()).offset(offset).limit(limit).all()


def update_plan(db: Session, plan: PreventionPlan, payload: PreventionPlanUpdate) -> PreventionPlan:
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(plan, key, value)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan
