from fastapi import APIRouter, Depends

from app.api.deps import require_api_token
from app.api.routes import (
    analyses,
    ct_analysis,
    health,
    labs,
    nudges,
    patients,
    plans,
    providers,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(
    ct_analysis.router,
    prefix="/ct",
    tags=["ct"],
    dependencies=[Depends(require_api_token)],
)
api_router.include_router(
    patients.router,
    prefix="/patients",
    tags=["patients"],
    dependencies=[Depends(require_api_token)],
)
api_router.include_router(
    providers.router,
    prefix="/providers",
    tags=["providers"],
    dependencies=[Depends(require_api_token)],
)
api_router.include_router(
    labs.router,
    prefix="/labs",
    tags=["labs"],
    dependencies=[Depends(require_api_token)],
)
api_router.include_router(
    analyses.router,
    prefix="/analyses",
    tags=["analyses"],
    dependencies=[Depends(require_api_token)],
)
api_router.include_router(
    plans.router,
    prefix="/plans",
    tags=["plans"],
    dependencies=[Depends(require_api_token)],
)
api_router.include_router(
    nudges.router,
    prefix="/nudges",
    tags=["nudges"],
    dependencies=[Depends(require_api_token)],
)
api_router.include_router(
    webhooks.router,
    prefix="/webhooks",
    tags=["webhooks"],
    dependencies=[Depends(require_api_token)],
)
