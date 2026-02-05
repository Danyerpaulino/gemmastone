from sqlalchemy.orm import Session

from app.db.models import Nudge, NudgeCampaign
from app.schemas.plan import NudgeCampaignCreate, NudgeCreate


def create_campaign(db: Session, payload: NudgeCampaignCreate) -> NudgeCampaign:
    campaign = NudgeCampaign(**payload.model_dump(exclude_unset=True))
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def create_nudges(db: Session, nudges: list[NudgeCreate]) -> list[Nudge]:
    db_items: list[Nudge] = []
    for payload in nudges:
        item = Nudge(**payload.model_dump(exclude_unset=True))
        db.add(item)
        db_items.append(item)
    db.commit()
    for item in db_items:
        db.refresh(item)
    return db_items
