from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.crud import patient as patient_crud
from app.db.session import get_db
from app.services.auth import decode_jwt_token, validate_session
from app.services.redis_client import get_redis

bearer_scheme = HTTPBearer(auto_error=False)


def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_token: str | None = Header(None),
) -> None:
    settings = get_settings()
    token = settings.api_token
    if not token:
        return

    provided = None
    if credentials and credentials.scheme.lower() == "bearer":
        provided = credentials.credentials
    elif x_api_token:
        provided = x_api_token

    if not provided or provided != token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
        )


def get_current_patient(
    request: Request,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    token = request.cookies.get(settings.jwt_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing session cookie.")

    try:
        payload = decode_jwt_token(token, verify_exp=True)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session.") from exc

    patient_id = payload.get("sub")
    if not patient_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session.")

    try:
        patient_uuid = UUID(str(patient_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session.") from exc

    redis_client = get_redis()
    if not validate_session(redis_client, str(patient_uuid), token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.")

    patient = patient_crud.get_patient(db, patient_uuid)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")
    return patient
