# StoneXero

**Voice-first kidney stone prevention platform powered by MedGemma and LangGraph.**

Built for the [MedGemma Impact Challenge](https://www.kaggle.com/competitions/med-gemma-impact-challenge) on Kaggle ($100K prize pool).

> 10% of Americans will experience a kidney stone. 50% will recur within 5 years. Yet only ~30% of patients adhere to prevention protocols. StoneXero bridges this gap with an AI agent that calls patients, texts them, and gets smarter over time — while giving providers a real-time compliance dashboard.

## How It Works

```
  Doctor's Office                    Patient's Phone                     Provider Dashboard
  ┌────────────┐                     ┌──────────────┐                   ┌─────────────────┐
  │            │                     │              │                   │                 │
  │  Patient   │  ── scans QR ──►   │  Signs up    │                   │  Sees patient   │
  │  gets QR   │                     │  (30 sec)    │                   │  auto-linked    │
  │  code      │                     │              │                   │                 │
  └────────────┘                     └──────┬───────┘                   │  Views:         │
                                            │                           │  - Adherence    │
                                    AI calls patient                    │  - Call logs    │
                                    (intake interview)                  │  - Risk level   │
                                            │                           │  - Lab trends   │
                                    ┌───────▼────────┐                  │                 │
                                    │  Ongoing:      │                  │  No invites     │
                                    │  - Daily SMS   │ ──── data ────► │  No setup       │
                                    │  - Weekly call │                  │  Just works     │
                                    │  - On-demand   │                  │                 │
                                    └────────────────┘                  └─────────────────┘
```

**Zero friction for both sides.** Patient scans a QR code and gets a phone call. Doctor prints a QR code and sees compliance data. No apps to install, no portals to remember.

## Architecture

| Component | Technology | Role |
|-----------|-----------|------|
| **Medical Brain** | MedGemma 1.5 4B on Vertex AI | Asynchronous clinical reasoning — analyzes CT scans, labs, transcripts to build personalized patient context |
| **Voice Agent** | Vapi + Telnyx SIP | Real-time phone calls for intake interviews, coaching, and on-demand Q&A |
| **SMS** | Telnyx | Daily medication reminders, hydration check-ins, dietary nudges |
| **CT Pipeline** | LangGraph (7-node workflow) | Stone detection, 3D modeling, treatment planning, prevention plans |
| **Backend API** | FastAPI on Cloud Run | Orchestrates all services, scheduled actions, webhook handling |
| **Frontend** | Next.js on Vercel | Minimalist patient portal (5 screens) + provider compliance dashboard |
| **Database** | PostgreSQL | All PHI — patient records, contexts, transcripts, compliance logs |
| **Cache** | Redis (Upstash) | Ephemeral non-PHI: OTPs, rate limits, sessions |
| **Storage** | Google Cloud Storage | CT uploads, QR code images, call recordings |

### Two-Brain Design

**Brain 1 — MedGemma (Slow, Deep):** Works in the background like a specialist reviewing a chart. Processes lab results, CT scans, conversation transcripts, and self-reported data. Produces comprehensive "patient context documents" with personalized recommendations.

**Brain 2 — Voice Agent (Fast, Conversational):** Talks to patients in real-time. Reads from the context document MedGemma already prepared. The patient gets a natural conversation; the deep medical reasoning happened hours ago.

## CT Analysis Pipeline

The 7-node LangGraph workflow processes CT uploads end-to-end:

1. **CT Analysis** — MedGemma-powered stone detection with HU characterization
2. **Stone Modeling** — 3D mesh generation via marching cubes (padded + Gaussian smoothed)
3. **Treatment Decision** — AUA/EAU guideline-based recommendations
4. **Lab Integration** — Crystallography and 24-hour urine analysis
5. **Prevention Planning** — Personalized dietary, medication, and lifestyle rules
6. **Education Generation** — Patient-friendly summaries via MedGemma
7. **Nudge Scheduling** — Behavioral engagement campaign setup

## Repo Structure

```
├── backend/                  FastAPI application
│   ├── app/
│   │   ├── api/routes/       REST endpoints (auth, CT, voice, SMS, patients, providers, etc.)
│   │   ├── workflows/        LangGraph pipeline + CT normalization
│   │   ├── services/         MedGemma client, storage, auth, messaging, scheduling
│   │   ├── crud/             Database operations
│   │   ├── db/               SQLAlchemy models
│   │   ├── schemas/          Pydantic validation models
│   │   └── core/             Settings and configuration
│   ├── alembic/              Database migrations
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                 Next.js application
│   ├── app/
│   │   ├── (patient)/        Patient portal (dashboard, labs, chat, plan, progress)
│   │   ├── provider/         Provider compliance dashboard
│   │   ├── login/            SMS OTP login
│   │   └── join/             QR code onboarding
│   ├── components/           React components (StoneMeshViewer, CTIntake, etc.)
│   └── lib/                  API client, auth helpers, types
├── medgemma-service/         Standalone MedGemma multimodal microservice
│   ├── Dockerfile
│   ├── deploy.sh             Cloud Run deployment script
│   └── README.md             Deployment and cost guide
├── scripts/                  Dev helpers (seed_demo.py, seed_compliance.py)
├── db/                       Database init scripts
├── docs/                     Architecture and competition notes
├── docker-compose.yml        Dev stack (Postgres + Redis + backend)
├── docker-compose.edge.yml   Edge deployment with local GPU
└── .env.example              Environment variable template
```

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 15+
- Redis

### Option 1: Docker Compose (recommended)

```bash
cp .env.example .env
# Edit .env with your settings (MEDGEMMA_MODE=mock for local dev)

docker compose up --build

# Run migrations
cd backend && alembic upgrade head

# Seed demo data
cd .. && .venv/bin/python scripts/seed_demo.py
```

### Option 2: Manual Setup

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

### MedGemma Modes

| Mode | Use Case | Setup |
|------|----------|-------|
| `mock` | Local development, no GPU needed | `MEDGEMMA_MODE=mock` (default in .env.example) |
| `http` | Dedicated MedGemma microservice | Deploy `medgemma-service/`, set `MEDGEMMA_HTTP_URL` |
| `vertex` | Google Cloud Vertex AI | Set project, endpoint, location vars |
| `local` | On-device GPU inference | Set `MEDGEMMA_MODEL_PATH` |

See [`medgemma-service/README.md`](medgemma-service/README.md) for GPU deployment details.

## HAI-DEF Model Usage

This project uses **MedGemma 1.5 4B** from Google's [Health AI Developer Foundations](https://developers.google.com/health-ai-developer-foundations):

- **CT scan analysis**: Multimodal stone detection, measurement, and HU characterization
- **Patient context generation**: Synthesizes medical records, labs, and conversation transcripts into personalized context documents
- **Education content**: Generates patient-friendly explanations of conditions and prevention plans
- **Prevention planning**: Produces dietary, medication, and lifestyle recommendations based on stone composition and lab results

## Key Technologies

- [MedGemma](https://huggingface.co/google/medgemma-1.5-4b-it) — Medical foundation model from Google
- [LangGraph](https://github.com/langchain-ai/langgraph) — Agentic workflow orchestration
- [Vapi](https://vapi.ai) — Voice agent platform
- [Telnyx](https://telnyx.com) — SMS and SIP telephony
- [FastAPI](https://fastapi.tiangolo.com) — Backend framework
- [Next.js](https://nextjs.org) — Frontend framework
- [Three.js](https://threejs.org) — 3D stone mesh visualization

## Disclaimer

This is a research prototype built for the MedGemma Impact Challenge. **Not for clinical use.** All medical recommendations should be reviewed by a licensed healthcare provider. Synthetic data is used for demonstration purposes.

## License

[Apache License 2.0](LICENSE)
