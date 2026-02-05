# Infra

## Edge deployment (local workstation)

Use `docker-compose.edge.yml` to run the backend + Postgres on a local device. This is intended
for demoing an edge workflow on a non-cloud machine.

### GPU (preferred edge demo)
- Install NVIDIA Container Toolkit on the host.
- Place MedGemma weights under `./models/medgemma-1.5-4b-it`.
- Run:
  - `MEDGEMMA_MODE=local docker compose -f docker-compose.edge.yml up --build`

### CPU / demo fallback
- Run:
  - `MEDGEMMA_MODE=mock docker compose -f docker-compose.edge.yml up --build`

The mock mode keeps the workflow runnable without GPU while still demonstrating the agentic
pipeline, nudge scheduling, and patient chat.
Messaging is demo-only by default (`MESSAGING_MODE=mock`).
