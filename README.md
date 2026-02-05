# KidneyStone AI

AI-assisted kidney stone imaging and management workflows built around MedGemma and LangGraph.

Status: scaffolded project structure and placeholder services. Not for clinical use.

## Repo layout
- backend/     FastAPI + LangGraph orchestrator
- frontend/    Next.js provider portal (placeholder)
- docs/        Competition and architecture notes
- db/          Database initialization and migrations (placeholder)
- infra/       Deployment notes (placeholder)
- scripts/     Dev helper scripts (placeholder)

## Quick start (dev)
Backend (from repo root):
- `cd backend`
- `python -m venv .venv`
- `source .venv/bin/activate`
- `pip install -r requirements.txt`
- `uvicorn app.main:app --reload --host 0.0.0.0 --port 8080`
  - If `API_TOKEN` is set, include `Authorization: Bearer <token>` or `X-API-Token: <token>` on all API calls.

Docker (backend + Postgres):
- `cp .env.example .env`
- `docker compose up --build`
- `cd backend && alembic upgrade head`

Frontend is a minimal placeholder. If you want a full Next.js scaffold, run:
- `cd frontend`
- `npx create-next-app@latest . --ts --app --eslint --tailwind --use-npm --force`

Demo access gate (frontend):
- Set `NEXT_PUBLIC_DEMO_PASSWORD` to enable a shared access code prompt.
- Set `NEXT_PUBLIC_API_TOKEN` to forward the API token in frontend requests.

## Notes
- This repo contains early scaffolding only. APIs and workflows are stubs.
- Handle PHI locally and secure all infrastructure before any real use.
