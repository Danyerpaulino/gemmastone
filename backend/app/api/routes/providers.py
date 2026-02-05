from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.crud import provider as provider_crud
from app.db.session import get_db
from app.schemas.provider import ProviderCreate, ProviderList, ProviderOut

router = APIRouter()


@router.post("/", response_model=ProviderOut, status_code=201)
def create_provider(
    payload: ProviderCreate,
    db: Session = Depends(get_db),
) -> ProviderOut:
    existing = provider_crud.get_provider_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="Provider email already exists")
    return provider_crud.create_provider(db, payload)


@router.get("/", response_model=ProviderList)
def list_providers(
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> ProviderList:
    items = provider_crud.list_providers(db, offset=offset, limit=limit)
    total = provider_crud.count_providers(db)
    return ProviderList(items=items, total=total)


@router.get("/{provider_id}", response_model=ProviderOut)
def get_provider(
    provider_id: UUID,
    db: Session = Depends(get_db),
) -> ProviderOut:
    provider = provider_crud.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider
