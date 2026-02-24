# Backend

FastAPI service that hosts the LangGraph workflow and model services.

## Structure
- app/main.py            FastAPI app entrypoint
- app/api/routes/        HTTP routes
- app/workflows/         LangGraph state + workflow graph
- app/services/          Model and DICOM service stubs
- app/core/              Settings and shared utilities

## Dev run
From `backend/`:
- `python -m venv .venv`
- `source .venv/bin/activate`
- `pip install -r requirements.txt`
- `uvicorn app.main:app --reload --host 0.0.0.0 --port 8080`
  - If `API_TOKEN` is set, include `Authorization: Bearer <token>` or `X-API-Token: <token>` on all API calls.

## MedGemma (Vertex by default)
The backend defaults to `MEDGEMMA_MODE=vertex`. For local/edge demos, override:
- `MEDGEMMA_MODE=mock` (no model calls)
- `MEDGEMMA_MODE=local` (loads local weights; GPU recommended)

Vertex settings:
- `MEDGEMMA_VERTEX_ENDPOINT` (required)
- `MEDGEMMA_VERTEX_PROJECT`
- `MEDGEMMA_VERTEX_LOCATION`

## CT storage (GCS streaming)
Uploads stream directly to GCS, then the workflow downloads and extracts into a temp
workspace for processing. Configure:
- `STORAGE_MODE=auto|gcs|local` (default `auto`; uses GCS if `GCS_BUCKET` is set)
- `GCS_BUCKET` (required for GCS mode)
- `GCS_PREFIX` (optional; default `ct-uploads`)
- `LOCAL_STORAGE_ROOT` (optional; default `data/ct_scans`)

### Signed URL flow (large CTs)
The frontend can request a signed URL (`/ct/sign-upload`), upload directly to GCS, and then
trigger `/ct/analyze-uri`. Ensure your bucket CORS allows `PUT` from the Vercel domain and
the `Content-Type` header.

## Database migrations (Alembic)
From `backend/`:
- `alembic upgrade head`

## Redis (OTP + sessions)
The voice agent pivot uses Redis for OTPs and session tracking:
- `REDIS_URL` (default `redis://localhost:6379/0`)

## Auth + OTP
OTP logins issue an httpOnly JWT cookie:
- `JWT_SECRET` (override `dev-secret` in prod)
- `JWT_ALGORITHM` (default `HS256`)
- `JWT_COOKIE_SECURE` (`true` for HTTPS)
- `OTP_LENGTH` (default `6`)
- `FRONTEND_BASE_URL` (used for QR codes, default `http://localhost:3000`)

## Telnyx (SMS + SIP)
Outbound SMS and inbound webhook handling use Telnyx:
- `TELNYX_API_KEY`
- `TELNYX_MESSAGING_PROFILE_ID`
- `TELNYX_PHONE_NUMBER`
- `TELNYX_SIP_CONNECTION_ID` (used by Vapi for voice routing)
- `MESSAGING_MODE` (`mock` or `live`)

## Vapi (Voice Agent)
Outbound calls and webhook events use Vapi:
- `VAPI_API_KEY`
- `VAPI_ASSISTANT_ID`
- `VAPI_PHONE_NUMBER_ID`
- `VAPI_WEBHOOK_SECRET`

## Scheduler (Scheduled Actions)
Scheduled actions drive outbound calls, SMS, and background tasks. In production,
configure Cloud Scheduler (or any cron) to call:
- `POST /api/internal/dispatch-actions` every 5 minutes

If `API_TOKEN` is set, include it as `Authorization: Bearer <token>` or `X-API-Token`.
