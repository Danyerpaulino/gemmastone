from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.settings import get_settings

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
