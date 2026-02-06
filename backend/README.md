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
