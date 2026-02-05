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

## Database migrations (Alembic)
From `backend/`:
- `alembic upgrade head`
