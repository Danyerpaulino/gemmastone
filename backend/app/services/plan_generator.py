"""Generate a PreventionPlan from an intake-call transcript.

Uses MedGemma to extract stone type and risk factors from the call,
then builds dietary, medication, and lifestyle recommendations using
the same clinical rules as the CT-based workflow.
"""
from __future__ import annotations

import json
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import PreventionPlan
from app.services.medgemma_client import MedGemmaClient
from app.workflows.kidney_stone import DIETARY_RULES, MEDICATION_RECOMMENDATIONS

logger = logging.getLogger(__name__)

VALID_STONE_TYPES = set(DIETARY_RULES.keys())
VALID_RISK_FACTORS = set(MEDICATION_RECOMMENDATIONS.keys())

EXTRACTION_PROMPT = """\
You are a clinical extraction assistant.  Analyze the following intake-call
transcript and summary for a kidney stone patient.

Extract:
1. stone_type – one of: calcium_oxalate, uric_acid, calcium_phosphate, cystine, struvite.
   If the patient describes calcium oxalate stones, choose calcium_oxalate, etc.
   If unclear, default to calcium_oxalate.
2. risk_factors – a list from: hypercalciuria, hypocitraturia, hyperuricosuria, acidic_urine.
   Include any that are mentioned or strongly implied by the transcript.

Return ONLY valid JSON (no markdown, no fences):
{{"stone_type": "...", "risk_factors": [...]}}

--- SUMMARY ---
{summary}

--- TRANSCRIPT ---
{transcript}
"""


async def generate_intake_plan(
    db: Session,
    patient_id: UUID,
    transcript: str,
    summary: str,
    medgemma: MedGemmaClient | None = None,
) -> PreventionPlan:
    """Create a prevention plan from an intake-call transcript."""
    client = medgemma or MedGemmaClient()

    # --- Step 1: extract stone type + risk factors via MedGemma ---
    extraction_prompt = EXTRACTION_PROMPT.format(
        summary=summary or "(no summary)",
        transcript=transcript or "(no transcript)",
    )
    raw = await client.generate_text(extraction_prompt)
    stone_type, risk_factors = _parse_extraction(raw)

    # --- Step 2: build recommendations from clinical rules ---
    rules = DIETARY_RULES.get(stone_type, DIETARY_RULES["calcium_oxalate"])

    fluid_target = rules["fluid_target_ml"]
    if "low_urine_volume" in risk_factors:
        fluid_target = max(fluid_target, 3500)

    dietary_recommendations = [
        {"category": "reduce", "items": rules["reduce"], "priority": "high"},
        {"category": "increase", "items": rules["increase"], "priority": "high"},
    ]

    medications = []
    for risk in risk_factors:
        if risk in MEDICATION_RECOMMENDATIONS:
            medications.append(MEDICATION_RECOMMENDATIONS[risk])

    lifestyle = [
        f"Drink at least {fluid_target}ml daily (goal urine output >2L/day).",
        "Spread fluid intake throughout the day, including before bed.",
        "Limit sodium intake to <2300mg daily (ideally <1500mg).",
        "Moderate animal protein to 0.8-1.0 g/kg body weight.",
        "Maintain a healthy body weight.",
        rules["special_instructions"],
    ]

    # --- Step 3: generate patient-friendly summary ---
    summary_prompt = (
        "Create a brief, patient-friendly explanation (6th grade reading level) of their "
        "kidney stone prevention plan.  Keep it under 200 words.\n"
        f"Stone type: {stone_type}.\n"
        f"Key dietary changes: reduce {', '.join(i['item'] for i in rules['reduce'][:3]) or 'N/A'}, "
        f"increase {', '.join(i['item'] for i in rules['increase'][:3]) or 'N/A'}.\n"
        f"Daily fluid goal: {fluid_target}ml.\n"
        f"Medications: {', '.join(m['name'] for m in medications) or 'none recommended yet'}.\n"
    )
    personalized_summary = await client.generate_text(summary_prompt)

    # --- Step 4: deactivate existing active plans ---
    db.query(PreventionPlan).filter(
        PreventionPlan.patient_id == patient_id,
        PreventionPlan.active == True,  # noqa: E712
    ).update({"active": False})

    # --- Step 5: save new plan ---
    plan = PreventionPlan(
        patient_id=patient_id,
        analysis_id=None,
        dietary_recommendations=dietary_recommendations,
        fluid_intake_target_ml=fluid_target,
        medications_recommended=medications,
        lifestyle_modifications=lifestyle,
        personalized_summary=personalized_summary,
        active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    logger.info(
        "Generated intake prevention plan %s for patient %s (stone_type=%s)",
        plan.id,
        patient_id,
        stone_type,
    )
    return plan


def _parse_extraction(raw: str) -> tuple[str, list[str]]:
    """Parse MedGemma extraction output into (stone_type, risk_factors)."""
    stone_type = "calcium_oxalate"
    risk_factors: list[str] = []

    if not raw:
        return stone_type, risk_factors

    cleaned = raw.strip()
    # Strip markdown fences if present
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        lines = cleaned.splitlines()
        if lines and lines[0].strip().lower().startswith("json"):
            cleaned = "\n".join(lines[1:])

    parsed = None
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass

    if isinstance(parsed, dict):
        raw_type = parsed.get("stone_type", "")
        if isinstance(raw_type, str) and raw_type in VALID_STONE_TYPES:
            stone_type = raw_type

        raw_risks = parsed.get("risk_factors", [])
        if isinstance(raw_risks, list):
            risk_factors = [r for r in raw_risks if isinstance(r, str) and r in VALID_RISK_FACTORS]

    return stone_type, risk_factors
