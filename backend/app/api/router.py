from fastapi import APIRouter, Depends

from app.api.deps import require_api_token
from app.api.routes import (
    analyses,
    auth,
    ct_analysis,
    context,
    health,
    labs,
    nudges,
    onboarding,
    patient_portal,
    scheduler,
    sms,
    patients,
    plans,
    providers,
    vapi_webhooks,
    voice,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
api_router.include_router(patient_portal.router, prefix="/patient", tags=["patient"])
api_router.include_router(sms.router, prefix="/webhooks/sms", tags=["sms"])
api_router.include_router(vapi_webhooks.router, prefix="/webhooks/vapi", tags=["vapi"])
api_router.include_router(
    ct_analysis.router,
    prefix="/ct",
    tags=["ct"],
    dependencies=[Depends(require_api_token)],
)
api_router.include_router(
    context.router,
    prefix="/context",
    tags=["context"],
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
    voice.router,
    prefix="/voice",
    tags=["voice"],
    dependencies=[Depends(require_api_token)],
)
api_router.include_router(
    nudges.router,
    prefix="/nudges",
    tags=["nudges"],
    dependencies=[Depends(require_api_token)],
)
api_router.include_router(
    scheduler.router,
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_api_token)],
)
api_router.include_router(
    webhooks.router,
    prefix="/webhooks",
    tags=["webhooks"],
    dependencies=[Depends(require_api_token)],
)
