from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

from langgraph.graph import END, StateGraph

from app.services.dicom_processor import DicomProcessor
from app.services.medgemma_client import MedGemmaClient
from app.workflows.state import KidneyStoneState

medgemma_client = MedGemmaClient()

STONE_TYPE_UNKNOWN = "unknown"

TREATMENT_MATRIX = {
    ("kidney_upper", "small"): "observation",
    ("kidney_upper", "medium"): "eswl",
    ("kidney_upper", "large"): "pcnl",
    ("kidney_lower", "small"): "observation",
    ("kidney_lower", "medium"): "ureteroscopy",
    ("kidney_lower", "large"): "pcnl",
    ("proximal_ureter", "small"): "medical_expulsive",
    ("proximal_ureter", "medium"): "ureteroscopy",
    ("distal_ureter", "small"): "medical_expulsive",
    ("distal_ureter", "medium"): "ureteroscopy",
}

SIZE_THRESHOLDS = {
    "small": (0, 5),
    "medium": (5, 20),
    "large": (20, float("inf")),
}

DIETARY_RULES = {
    "calcium_oxalate": {
        "reduce": [
            {"item": "spinach", "reason": "Very high oxalate"},
            {"item": "rhubarb", "reason": "Very high oxalate"},
            {"item": "nuts (especially almonds)", "reason": "High oxalate"},
            {"item": "chocolate", "reason": "High oxalate"},
            {"item": "black tea", "reason": "Moderate oxalate"},
        ],
        "increase": [
            {"item": "citrus fruits (lemon, orange)", "reason": "Increases urinary citrate"},
            {"item": "calcium-rich foods WITH meals", "reason": "Binds oxalate in gut"},
        ],
        "fluid_target_ml": 3000,
        "special_instructions": (
            "Pair calcium-rich foods with oxalate-containing meals to bind oxalate in the gut."
        ),
    },
    "uric_acid": {
        "reduce": [
            {"item": "red meat", "reason": "High purine content"},
            {"item": "organ meats (liver, kidney)", "reason": "Very high purine"},
            {"item": "shellfish", "reason": "High purine"},
            {"item": "beer and alcohol", "reason": "Increases uric acid, dehydrates"},
        ],
        "increase": [
            {"item": "vegetables", "reason": "Alkalinizes urine"},
            {"item": "low-fat dairy", "reason": "May reduce uric acid"},
            {"item": "citrus fruits", "reason": "Alkalinizes urine"},
        ],
        "fluid_target_ml": 3000,
        "special_instructions": "Goal urine pH 6.5-7.0. Uric acid stones can dissolve.",
    },
    "calcium_phosphate": {
        "reduce": [
            {"item": "sodium/salt", "reason": "Increases calcium excretion"},
            {"item": "animal protein", "reason": "Acidifies urine"},
        ],
        "increase": [
            {"item": "citrus fruits", "reason": "Citrate inhibits stone formation"},
        ],
        "fluid_target_ml": 2500,
        "special_instructions": "Consider evaluation for hyperparathyroidism or RTA.",
    },
    "cystine": {
        "reduce": [
            {"item": "sodium", "reason": "Increases cystine excretion"},
            {"item": "animal protein", "reason": "Contains methionine"},
        ],
        "increase": [
            {"item": "fluids (dramatic increase)", "reason": "Dilute cystine concentration"},
        ],
        "fluid_target_ml": 4000,
        "special_instructions": "Genetic condition. May need alkalinization + tiopronin.",
    },
    "struvite": {
        "reduce": [],
        "increase": [],
        "fluid_target_ml": 2500,
        "special_instructions": (
            "Caused by UTI with urease-producing bacteria; treat infection aggressively."
        ),
    },
}

MEDICATION_RECOMMENDATIONS = {
    "hypercalciuria": {
        "name": "hydrochlorothiazide",
        "dose": "25mg daily",
        "rationale": "Thiazides reduce urinary calcium excretion",
    },
    "hypocitraturia": {
        "name": "potassium citrate",
        "dose": "20 mEq twice daily",
        "rationale": "Citrate inhibits stones and alkalinizes urine",
    },
    "hyperuricosuria": {
        "name": "allopurinol",
        "dose": "300mg daily",
        "rationale": "Reduces uric acid production",
    },
    "acidic_urine": {
        "name": "potassium citrate",
        "dose": "10-20 mEq twice daily",
        "rationale": "Alkalinizes urine for uric acid/cystine stones",
    },
}


async def ct_analysis_node(state: KidneyStoneState) -> KidneyStoneState:
    ct_path = Path(state["ct_scan_path"])
    volume = DicomProcessor.load_series(ct_path)

    prompt = (
        "Analyze this CT scan for kidney stones. For each stone identified, return JSON with: "
        "location (kidney upper/mid/lower pole or ureter proximal/mid/distal), "
        "maximum size in mm, Hounsfield units, and shape. "
        "Also include hydronephrosis severity if present. "
        "Return {\"stones\": [...], \"confidence\": 0-1}."
    )

    result = await medgemma_client.analyze_ct(volume, prompt, modality="CT")
    stones = result.get("stones_detected") or result.get("stones") or []

    for stone in stones:
        if "predicted_composition" not in stone and stone.get("hounsfield_units") is not None:
            stone["predicted_composition"] = _predict_composition_from_hu(
                float(stone["hounsfield_units"])
            )

    predicted = result.get("predicted_composition") or _aggregate_composition(stones)
    confidence = float(result.get("confidence", 0.6)) if stones else 0.2

    return {
        **state,
        "stones_detected": stones,
        "predicted_composition": predicted,
        "composition_confidence": confidence,
    }


async def stone_modeling_node(state: KidneyStoneState) -> KidneyStoneState:
    return state


async def treatment_decision_node(state: KidneyStoneState) -> KidneyStoneState:
    stones = state.get("stones_detected") or []
    if not stones:
        return {
            **state,
            "treatment_recommendation": "observation",
            "treatment_rationale": "No stones detected on the current scan.",
            "urgency_level": "routine",
        }

    primary = _identify_primary_stone(stones)
    size_category = _categorize_size(primary.get("size_mm"))
    location = _normalize_location(primary.get("location"))

    treatment = TREATMENT_MATRIX.get((location, size_category), "ureteroscopy")
    treatment = _adjust_for_composition(
        treatment, state.get("predicted_composition", STONE_TYPE_UNKNOWN), primary.get("size_mm")
    )

    urgency = _assess_urgency(stones)
    rationale = (
        f"Primary stone {primary.get('size_mm')}mm in {primary.get('location')} with "
        f"composition {state.get('predicted_composition', STONE_TYPE_UNKNOWN)}."
    )

    return {
        **state,
        "treatment_recommendation": treatment,
        "treatment_rationale": rationale,
        "urgency_level": urgency,
    }


async def lab_integration_node(state: KidneyStoneState) -> KidneyStoneState:
    crystallography = state.get("crystallography_results") or {}
    urine_results = state.get("urine_24hr_results") or {}

    risk_factors = set(state.get("metabolic_risk_factors") or [])

    lab_composition = None
    for key in ("composition", "stone_type", "stone_composition", "primary_composition"):
        value = crystallography.get(key)
        if value:
            lab_composition = value
            break

    normalized = _normalize_composition(lab_composition)
    if normalized != STONE_TYPE_UNKNOWN:
        state = {
            **state,
            "predicted_composition": normalized,
            "composition_confidence": max(state.get("composition_confidence", 0.0), 0.9),
        }

    urine_calcium = _parse_float(
        urine_results.get("calcium_mg_day")
        or urine_results.get("urine_calcium_mg_day")
        or urine_results.get("calcium")
    )
    if urine_calcium is not None and urine_calcium > 250:
        risk_factors.add("hypercalciuria")

    urine_citrate = _parse_float(
        urine_results.get("citrate_mg_day")
        or urine_results.get("urine_citrate_mg_day")
        or urine_results.get("citrate")
    )
    if urine_citrate is not None and urine_citrate < 320:
        risk_factors.add("hypocitraturia")

    urine_uric = _parse_float(
        urine_results.get("uric_acid_mg_day")
        or urine_results.get("urine_uric_acid_mg_day")
        or urine_results.get("uric_acid")
    )
    if urine_uric is not None and urine_uric > 750:
        risk_factors.add("hyperuricosuria")

    urine_ph = _parse_float(
        urine_results.get("ph")
        or urine_results.get("urine_ph")
        or urine_results.get("pH")
    )
    if urine_ph is not None and urine_ph < 5.5:
        risk_factors.add("acidic_urine")

    return {
        **state,
        "metabolic_risk_factors": sorted(risk_factors),
    }


async def prevention_planning_node(state: KidneyStoneState) -> KidneyStoneState:
    composition = state.get("predicted_composition", STONE_TYPE_UNKNOWN)
    rules = DIETARY_RULES.get(composition, DIETARY_RULES["calcium_oxalate"])
    risk_factors = state.get("metabolic_risk_factors", [])

    medications = []
    for risk in risk_factors:
        if risk in MEDICATION_RECOMMENDATIONS:
            medications.append(MEDICATION_RECOMMENDATIONS[risk])

    lifestyle = [
        f"Drink at least {rules['fluid_target_ml']}ml daily (goal urine output >2L/day).",
        "Spread fluid intake throughout the day, including before bed.",
        "Limit sodium intake to <2300mg daily (ideally <1500mg).",
        "Moderate animal protein to 0.8-1.0 g/kg body weight.",
        "Maintain a healthy body weight.",
        rules["special_instructions"],
    ]

    dietary_recommendations = [
        {"category": "reduce", "items": rules["reduce"], "priority": "high"},
        {"category": "increase", "items": rules["increase"], "priority": "high"},
    ]

    return {
        **state,
        "dietary_recommendations": dietary_recommendations,
        "fluid_intake_target_ml": rules["fluid_target_ml"],
        "medications_recommended": medications,
        "lifestyle_modifications": lifestyle,
    }


async def education_generation_node(state: KidneyStoneState) -> KidneyStoneState:
    stones = state.get("stones_detected") or [{}]
    primary = stones[0] if stones else {}
    prompt = (
        "Create a patient-friendly explanation (6th grade reading level) about their kidney "
        "stone type and prevention plan. "
        f"Stone type: {state.get('predicted_composition', STONE_TYPE_UNKNOWN)}. "
        f"Stone size: {primary.get('size_mm', 'unknown')}mm. "
        f"Location: {primary.get('location', 'unknown')}. "
        f"Treatment: {state.get('treatment_recommendation', 'observation')}. "
        f"Fluid goal: {state.get('fluid_intake_target_ml', 2500)}ml daily. "
        "Be encouraging and concise."
    )

    try:
        summary = await medgemma_client.generate_text(prompt)
    except Exception:
        summary = (
            "You have a kidney stone. Staying hydrated and following your plan can help prevent "
            "future stones. Your care team will guide treatment options based on size and location."
        )

    materials = [
        {
            "type": "pdf",
            "title": "Understanding Kidney Stones",
            "url": "/materials/kidney-stones-101.pdf",
            "description": "Overview of kidney stone disease",
        },
        {
            "type": "pdf",
            "title": "Hydration Guide",
            "url": "/materials/hydration-guide.pdf",
            "description": "Tips for meeting your fluid goals",
        },
    ]

    return {
        **state,
        "personalized_summary": summary,
        "education_materials": materials,
    }


async def nudge_scheduling_node(state: KidneyStoneState) -> KidneyStoneState:
    treatment = state.get("treatment_recommendation")
    fluid_goal = state.get("fluid_intake_target_ml", 2500)
    now = datetime.utcnow()

    nudges = [
        {
            "time": now + timedelta(hours=2),
            "channel": "sms",
            "template": "welcome",
            "message": f"Welcome! Your daily water goal is {fluid_goal}ml.",
            "type": "onboarding",
        },
        {
            "time": now + timedelta(days=1, hours=9),
            "channel": "sms",
            "template": "hydration_morning",
            "message": "Good morning! Start with a big glass of water.",
            "type": "hydration_reminder",
        },
        {
            "time": now + timedelta(days=3),
            "channel": "sms",
            "template": "engagement_check",
            "message": "How is hydration going? Reply YES if you hit your goal yesterday.",
            "type": "engagement",
            "expects_response": True,
        },
    ]

    if treatment == "medical_expulsive":
        nudges.append(
            {
                "time": now + timedelta(days=1, hours=21),
                "channel": "sms",
                "template": "medication_reminder",
                "message": "Time for your tamsulosin. Take at bedtime to minimize dizziness.",
                "type": "medication",
            }
        )

    checkpoints = [
        {
            "day": 30,
            "action": "24hr_urine_recheck",
            "description": "Repeat 24-hour urine to verify improvements",
        },
        {
            "day": 180,
            "action": "imaging_followup",
            "description": "Ultrasound to check for new stone formation",
        },
    ]

    return {
        **state,
        "nudge_schedule": nudges,
        "compliance_checkpoints": checkpoints,
    }


@lru_cache
def build_workflow():
    graph = StateGraph(KidneyStoneState)

    graph.add_node("ct_analysis", ct_analysis_node)
    graph.add_node("stone_modeling", stone_modeling_node)
    graph.add_node("treatment_decision", treatment_decision_node)
    graph.add_node("lab_integration", lab_integration_node)
    graph.add_node("prevention_planning", prevention_planning_node)
    graph.add_node("education_generation", education_generation_node)
    graph.add_node("nudge_scheduling", nudge_scheduling_node)

    graph.set_entry_point("ct_analysis")
    graph.add_edge("ct_analysis", "stone_modeling")
    graph.add_edge("stone_modeling", "treatment_decision")
    graph.add_conditional_edges(
        "treatment_decision",
        _labs_available,
        {
            "lab_integration": "lab_integration",
            "prevention_planning": "prevention_planning",
        },
    )
    graph.add_edge("lab_integration", "prevention_planning")
    graph.add_edge("prevention_planning", "education_generation")
    graph.add_edge("education_generation", "nudge_scheduling")
    graph.add_edge("nudge_scheduling", END)

    return graph.compile()


def _predict_composition_from_hu(hu: float) -> str:
    if hu < 500:
        return "uric_acid"
    if 500 <= hu < 700:
        return "cystine"
    if 700 <= hu < 1000:
        return "calcium_oxalate"
    return "calcium_phosphate"


def _aggregate_composition(stones: list[dict]) -> str:
    if not stones:
        return STONE_TYPE_UNKNOWN
    for stone in stones:
        if stone.get("predicted_composition"):
            return stone["predicted_composition"]
    return STONE_TYPE_UNKNOWN


def _identify_primary_stone(stones: list[dict]) -> dict:
    return max(stones, key=lambda s: float(s.get("size_mm", 0) or 0))


def _categorize_size(size_mm) -> str:
    size = float(size_mm or 0)
    for category, (low, high) in SIZE_THRESHOLDS.items():
        if low <= size < high:
            return category
    return "medium"


def _normalize_location(location: str | None) -> str:
    if not location:
        return "kidney_upper"
    loc = location.lower()
    if "upper" in loc and "kidney" in loc:
        return "kidney_upper"
    if "lower" in loc and "kidney" in loc:
        return "kidney_lower"
    if "proximal" in loc or "upper ureter" in loc:
        return "proximal_ureter"
    if "distal" in loc or "lower ureter" in loc:
        return "distal_ureter"
    if "ureter" in loc:
        return "proximal_ureter"
    return "kidney_upper"


def _adjust_for_composition(treatment: str, composition: str, size_mm) -> str:
    size = float(size_mm or 0)
    if composition == "uric_acid" and size < 15:
        return "medical_expulsive"
    if composition == "struvite" and size > 10:
        return "pcnl"
    return treatment


def _assess_urgency(stones: list[dict]) -> str:
    for stone in stones:
        if stone.get("hydronephrosis") == "severe":
            return "emergent"
        if stone.get("complete_obstruction"):
            return "emergent"
    total_burden = sum(float(s.get("size_mm", 0) or 0) for s in stones)
    if total_burden > 30:
        return "urgent"
    return "routine"


def _labs_available(state: KidneyStoneState) -> str:
    if state.get("crystallography_results") or state.get("urine_24hr_results"):
        return "lab_integration"
    return "prevention_planning"


def _normalize_composition(value) -> str:
    if not value:
        return STONE_TYPE_UNKNOWN
    text = str(value).strip().lower()
    if "oxalate" in text:
        return "calcium_oxalate"
    if "phosphate" in text:
        return "calcium_phosphate"
    if "uric" in text:
        return "uric_acid"
    if "struvite" in text:
        return "struvite"
    if "cystine" in text:
        return "cystine"
    if "mixed" in text:
        return "mixed"
    return STONE_TYPE_UNKNOWN


def _parse_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
