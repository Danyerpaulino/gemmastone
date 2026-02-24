from sqlalchemy.orm import Session

from app.db.models import Provider
from app.schemas.provider import ProviderCreate
from app.services.referral_codes import generate_qr_code_url, generate_referral_code


def create_provider(db: Session, payload: ProviderCreate) -> Provider:
    provider = Provider(**payload.model_dump(exclude_unset=True))
    referral_code = generate_referral_code(provider.name)
    while get_provider_by_referral_code(db, referral_code):
        referral_code = generate_referral_code(provider.name)
    provider.referral_code = referral_code
    try:
        provider.qr_code_url = generate_qr_code_url(referral_code)
    except Exception:
        provider.qr_code_url = None
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def get_provider(db: Session, provider_id) -> Provider | None:
    return db.query(Provider).filter(Provider.id == provider_id).first()


def get_provider_by_email(db: Session, email: str) -> Provider | None:
    return db.query(Provider).filter(Provider.email == email).first()


def get_provider_by_referral_code(db: Session, referral_code: str) -> Provider | None:
    return db.query(Provider).filter(Provider.referral_code == referral_code).first()


def list_providers(db: Session, offset: int = 0, limit: int = 100) -> list[Provider]:
    return db.query(Provider).offset(offset).limit(limit).all()


def count_providers(db: Session) -> int:
    return db.query(Provider).count()
