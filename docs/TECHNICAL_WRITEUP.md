# KidneyStone AI: Voice-First Kidney Stone Prevention Powered by MedGemma

**MedGemma Impact Challenge — Technical Overview**
**Team:** Aaron Gore (Team Lead), Dr. Ilya Sobol (Urologist), Danyer Paulino (Technical Lead), Len Zheleznyak (Strategist)
**Repository:** [github.com/danyerpaulino/kidneystone-ai](https://github.com/Danyerpaulino/kidneystone-ai) | **Demo:** [kidneystone-ai.vercel.app](https://kidneystone-ai.vercel.app)

---

## 1. Problem: The Prevention Gap

Kidney stones affect 1 in 10 Americans, with a 50% recurrence rate within five years. Evidence-based prevention — hydration, dietary changes, medication — can reduce recurrence by 40-60% (NNT 2.5-8), yet adherence sits at roughly 30%. Only 7% of stone patients receive a metabolic evaluation. The failure is not in medical knowledge but in patient engagement: people leave the ER, get no follow-up, and form another stone.

**KidneyStone AI addresses this gap.** Instead of relying on patients to remember appointments and download apps, an AI agent proactively calls them, texts them daily reminders, and adapts its guidance using MedGemma's medical reasoning. Providers get a real-time compliance dashboard with zero setup.

## 2. Architecture: Two-Brain Design

The core architectural insight is separating **deep medical reasoning** from **real-time conversation**.

```
                  ┌──────────────────────────────────┐
                  │       MedGemma (Brain 1)          │
                  │     Asynchronous, Deep Reasoning   │
                  │                                    │
                  │  CT scans ──► Stone analysis        │
                  │  Lab results ──► Risk assessment    │
                  │  Transcripts ──► Updated context    │
                  │                                    │
                  │  Output: Patient Context Document   │
                  └──────────────┬───────────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────────┐
                  │     Voice Agent (Brain 2)         │
                  │     Real-Time, Conversational      │
                  │                                    │
                  │  Reads pre-built context            │
                  │  Conducts phone calls               │
                  │  Answers patient questions           │
                  │  Reports back to MedGemma            │
                  └──────────────────────────────────┘
```

**Brain 1 — MedGemma** operates asynchronously, like a specialist reviewing charts overnight. It processes CT scans (multimodal), lab results, voice call transcripts, and self-reported data. It produces a comprehensive patient context document — a structured summary of the patient's medical story, risk factors, stone composition analysis, and personalized recommendations. This runs on Google Cloud Run with an L4 GPU via a custom multimodal inference service (the default Vertex AI Model Garden deployment uses vLLM, which is text-only — we built a HuggingFace Transformers-based service to enable image input).

**Brain 2 — Voice Agent** talks to patients in real-time via Vapi (voice) and Telnyx (SMS/SIP). It reads the context document MedGemma already prepared, so the patient experiences a natural, knowledgeable conversation without waiting for inference. After each interaction, the transcript feeds back to MedGemma for context refinement.

This separation means MedGemma can take 30-60 seconds for deep analysis without affecting conversation quality, and the voice agent stays under 500ms response times.

## 3. MedGemma Integration: Four Capabilities

### 3a. CT Scan Analysis (Multimodal)

A 7-node LangGraph workflow orchestrates the full analysis pipeline:

1. **CT Analysis** — MedGemma analyzes DICOM slices (converted to PNG) to detect stones, estimate size in millimeters, characterize Hounsfield units, and identify location (kidney upper/lower pole, proximal/distal ureter). Output normalization handles MedGemma's variable response formats (coordinates as dicts or lists, bounding boxes as nested objects).

2. **3D Stone Modeling** — Detected stones are segmented into binary masks, padded (3 voxels to ensure surface closure), Gaussian-smoothed (σ=1.0), and converted to 3D meshes via marching cubes. The frontend renders these meshes in Three.js for interactive visualization.

3. **Treatment Decision** — Maps stone size, location, and composition against AUA/EAU guideline matrices to recommend observation, medical expulsive therapy, ESWL, ureteroscopy, or PCNL.

4. **Lab Integration** — Ingests crystallography results and 24-hour urine panels. MedGemma correlates lab findings with CT analysis for confirmed stone typing.

5. **Prevention Planning** — Generates personalized dietary rules (stone-type-specific), medication recommendations, fluid targets, and lifestyle modifications.

6. **Education Generation** — MedGemma produces patient-friendly explanations at appropriate reading levels.

7. **Nudge Scheduling** — Sets up a behavioral engagement campaign (SMS reminders, follow-up calls) based on the prevention plan.

### 3b. Patient Context Documents

After each significant event (onboarding, voice call, lab upload, CT analysis), MedGemma rebuilds a structured context document containing: medical history summary, current risk assessment, active prevention plan, recent compliance trends, and conversation guidance for the voice agent. This is stored in PostgreSQL (PHI-safe) and injected into the voice agent's system prompt at call time.

### 3c. Text Generation

MedGemma generates patient education content, SMS message content for nudges, and clinical summaries for the provider dashboard.

### 3d. Clinical Reasoning

For the prevention planning node, MedGemma combines stone composition data, lab values, dietary history (from intake interviews), and AUA/EAU guidelines to produce evidence-based, personalized recommendations — not generic advice, but specific to the patient's stone type and metabolic profile.

## 4. Patient Journey

**Onboarding (30 seconds):** Provider hands patient a QR code card. Patient scans it, enters name and phone number, receives SMS OTP verification. Patient is auto-linked to their provider — no invites, no app downloads.

**Intake (10-15 minutes):** The AI agent calls the patient for a structured interview: stone history, current diet, fluid intake, medications, lifestyle factors. The transcript is processed by MedGemma to build the initial context document and prevention plan.

**Ongoing engagement:** Daily SMS reminders (hydration, medications). Weekly coaching calls. On-demand Q&A (patient can text or call the agent anytime — "Can I eat almonds?"). Every interaction feeds back into MedGemma for context refinement.

**Provider visibility:** The compliance dashboard shows adherence scores, risk-sorted patient lists, call transcripts, lab trends, and prevention plan status — all populated automatically.

## 5. Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| AI Model | MedGemma 1.5 4B (multimodal) | Custom Cloud Run service with L4 GPU; also supports local/mock modes |
| Workflow | LangGraph | 7-node stateful pipeline with conditional routing |
| Backend | FastAPI on Cloud Run | 17 route modules, async webhook handling |
| Frontend | Next.js on Vercel | Patient portal (5 screens) + provider dashboard |
| Voice | Vapi + Telnyx SIP | Outbound/inbound calls, intake interviews |
| SMS | Telnyx | Bidirectional messaging, OTP auth |
| Database | PostgreSQL | All PHI, SQLAlchemy ORM, Alembic migrations |
| Cache | Redis (Upstash) | Ephemeral non-PHI: OTPs, sessions, rate limits |
| Storage | Google Cloud Storage | CT uploads with signed URLs, QR images |
| 3D Viz | Three.js | Interactive stone mesh rendering in browser |

## 6. Deployment and Reproducibility

The repository includes:
- `docker-compose.yml` for local development (PostgreSQL + Redis + backend)
- `docker-compose.edge.yml` for edge deployment with local GPU inference
- `medgemma-service/` with Dockerfile and deploy scripts for Cloud Run GPU
- `scripts/seed_demo.py` to generate synthetic CT data and seed the database
- `.env.example` with all configuration variables documented
- `MEDGEMMA_MODE=mock` for running without GPU access

All external services (Vapi, Telnyx, MedGemma) have mock fallbacks, so the system can be evaluated locally without API keys or GPU hardware.

## 7. Impact Potential

At modest scale (500K patients, 20-point adherence improvement): an estimated 55,000 stone events prevented annually, saving $462M in emergency and surgical costs. The voice-first approach eliminates the primary barrier — app fatigue — by meeting patients on the device they already use: their phone. The provider QR code system eliminates the enrollment friction that kills most digital health tools.

The system is designed for the real world: PHI stays in PostgreSQL (GCP BAA-covered), Redis holds only ephemeral non-medical data, and the two-brain architecture keeps costs manageable by running MedGemma asynchronously rather than in the critical path of every conversation.

---

*KidneyStone AI is a research prototype. Not for clinical use. All medical recommendations should be reviewed by a licensed healthcare provider.*
