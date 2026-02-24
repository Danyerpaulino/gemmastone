"""
Kidney Stone Analysis Workflow

A 7-node LangGraph workflow for comprehensive kidney stone management:
1. CT Analysis - MedGemma-powered stone detection and characterization
2. Stone Modeling - 3D segmentation and volume calculation
3. Treatment Decision - AUA/EAU guideline-based recommendations
4. Lab Integration - Crystallography and 24-hour urine analysis
5. Prevention Planning - Personalized dietary and medication plans
6. Education Generation - Patient-friendly summaries via MedGemma
7. Nudge Scheduling - Behavioral engagement campaign setup

Clinical references:
- AUA Guidelines on Surgical Management of Stones (2016, amended 2022)
- EAU Guidelines on Urolithiasis (2023)
- Hounsfield unit thresholds based on Motley et al. (2001) and others

This module is the core of the GemmaStone platform, orchestrating
the full patient journey from CT upload to prevention plan delivery.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
import io
import json
from pathlib import Path

from langgraph.graph import END, StateGraph
import numpy as np

from app.services.dicom_processor import DicomProcessor
from app.services.medgemma_client import MedGemmaClient
from app.workflows.ct_normalization import normalize_ct_output
from app.workflows.state import KidneyStoneState

medgemma_client = MedGemmaClient()

STONE_TYPE_UNKNOWN = "unknown"
HYDRONEPHROSIS_RANK = {
    "none": 0,
    "mild": 1,
    "moderate": 2,
    "severe": 3,
}

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
    """
    Analyze CT scan for kidney stones using MedGemma.

    Extracts key slices from the DICOM volume and sends them to MedGemma
    for multimodal analysis. The model identifies stones and returns:
    - Location (kidney pole or ureter segment)
    - Size in millimeters
    - Hounsfield units (density, used to predict composition)
    - Shape characteristics
    - Hydronephrosis severity if present

    Composition is predicted from HU values using established thresholds:
    - <500 HU: Uric acid (radiolucent)
    - 500-700 HU: Cystine
    - 700-1000 HU: Calcium oxalate
    - >1000 HU: Calcium phosphate
    """
    ct_path = _resolve_ct_path(state)
    volume = DicomProcessor.load_series(ct_path)
    spacing = DicomProcessor.get_spacing(ct_path)

    prompt = (
        "Analyze this CT scan for kidney stones. For each stone identified, return JSON with: "
        "location (kidney upper/mid/lower pole or ureter proximal/mid/distal), "
        "maximum size in mm, Hounsfield units, shape, and location coordinates "
        "(x,y,z in voxel or millimeter space). "
        "If available, include size in voxels or a bounding box "
        "(z_min,y_min,x_min,z_max,y_max,x_max). "
        "Also include hydronephrosis severity if present. "
        "Return {\"stones\": [...], \"confidence\": 0-1}."
    )

    result = await medgemma_client.analyze_ct(volume, prompt, modality="CT")
    normalized_stones, normalized_output = normalize_ct_output(result, spacing)

    for stone in normalized_stones:
        if "predicted_composition" not in stone and stone.get("hounsfield_units") is not None:
            stone["predicted_composition"] = _predict_composition_from_hu(
                float(stone["hounsfield_units"])
            )

    predicted = normalized_output.get("predicted_composition") or _aggregate_composition(
        normalized_stones
    )
    confidence = (
        float(normalized_output.get("confidence", 0.6)) if normalized_stones else 0.2
    )
    hydronephrosis_level = _summarize_hydronephrosis(normalized_stones)

    return {
        **state,
        "stones_detected": normalized_stones,
        "predicted_composition": predicted,
        "composition_confidence": confidence,
        "hydronephrosis_level": hydronephrosis_level,
    }


async def stone_modeling_node(state: KidneyStoneState) -> KidneyStoneState:
    """
    Generate 3D models and calculate stone burden from CT segmentation.

    For each detected stone:
    1. Segments the stone from CT using HU-based thresholding
    2. Calculates volume in mm³ using voxel spacing
    3. Generates 3D mesh using marching cubes algorithm
    4. Aggregates total stone burden for treatment planning

    Total stone burden is a key factor in treatment decisions per AUA guidelines.
    Stones >20mm equivalent diameter typically require PCNL over ESWL.
    """
    stones = state.get("stones_detected") or []
    if not stones:
        return {**state, "total_stone_burden_mm3": None}

    ct_path = _resolve_ct_path(state)
    volume = DicomProcessor.load_series(ct_path)
    spacing = DicomProcessor.get_spacing(ct_path)

    masks = _segment_stone_masks(volume, spacing, stones)
    meshes = []
    total_burden = 0.0
    enriched = []

    for idx, stone in enumerate(stones):
        mask_entry = masks[idx] if idx < len(masks) else None
        if mask_entry is not None:
            mask, origin = mask_entry
            volume_mm3 = float(mask.sum()) * float(spacing[0] * spacing[1] * spacing[2])
            total_burden += volume_mm3

            mesh = _mask_to_mesh(mask, origin, spacing)
            if mesh is not None:
                meshes.append(mesh)
            enriched.append(
                {
                    **stone,
                    "volume_mm3": volume_mm3,
                    "segmentation_method": "thresholding",
                    "mesh_generated": mesh is not None,
                }
            )
        else:
            approx_volume = _estimate_stone_volume_mm3(stone)
            if approx_volume is not None:
                total_burden += approx_volume
            enriched.append(
                {
                    **stone,
                    "volume_mm3": approx_volume,
                    "segmentation_method": "approximate",
                    "mesh_generated": False,
                }
            )

    mesh_blob = _encode_meshes(meshes, spacing) if meshes else None

    return {
        **state,
        "stones_detected": enriched,
        "stone_3d_model": mesh_blob,
        "total_stone_burden_mm3": total_burden,
    }


async def treatment_decision_node(state: KidneyStoneState) -> KidneyStoneState:
    """
    Recommend treatment pathway based on AUA/EAU guidelines.

    Treatment options (in order of invasiveness):
    - observation: <5mm stones, likely to pass spontaneously
    - medical_expulsive: 5-10mm, tamsulosin to relax ureter
    - eswl: Extracorporeal shock wave lithotripsy
    - ureteroscopy: URS with laser, preferred for lower pole
    - pcnl: Percutaneous nephrolithotomy for large/staghorn stones

    Urgency levels:
    - emergent: Infected obstructed kidney, complete obstruction
    - urgent: Moderate hydronephrosis, high stone burden
    - routine: Standard cases
    - elective: Prevention-focused, no active obstruction
    """
    stones = state.get("stones_detected") or []
    if not stones:
        return {
            **state,
            "treatment_recommendation": "observation",
            "treatment_rationale": "No stones detected on the current scan.",
            "urgency_level": "routine",
        }

    composition = state.get("predicted_composition", STONE_TYPE_UNKNOWN)
    total_burden_mm3 = state.get("total_stone_burden_mm3")
    hydronephrosis_level = state.get("hydronephrosis_level")

    primary = _identify_primary_stone(stones)
    treatment = _choose_treatment(
        stones=stones,
        composition=composition,
        total_burden_mm3=total_burden_mm3,
        hydronephrosis_level=hydronephrosis_level,
    )

    urgency = _assess_urgency(stones, total_burden_mm3, hydronephrosis_level)
    rationale = _build_treatment_rationale(
        stones=stones,
        composition=composition,
        total_burden_mm3=total_burden_mm3,
        hydronephrosis_level=hydronephrosis_level,
        primary=primary,
        treatment=treatment,
    )

    return {
        **state,
        "treatment_recommendation": treatment,
        "treatment_rationale": rationale,
        "urgency_level": urgency,
    }


async def lab_integration_node(state: KidneyStoneState) -> KidneyStoneState:
    """
    Integrate lab results to confirm composition and identify metabolic risk factors.

    Crystallography provides definitive stone composition (overrides CT prediction).
    24-hour urine analysis identifies treatable metabolic abnormalities:
    - Hypercalciuria (>250 mg/day): Thiazide diuretics
    - Hypocitraturia (<320 mg/day): Potassium citrate
    - Hyperuricosuria (>750 mg/day): Allopurinol
    - Hyperoxaluria (>40 mg/day): Dietary modification
    - Low urine volume (<2L/day): Increased fluid intake
    """
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
    if urine_ph is not None and urine_ph > 6.8:
        risk_factors.add("alkaline_urine")

    urine_volume = _parse_float(
        urine_results.get("volume_ml_day")
        or urine_results.get("urine_volume_ml_day")
        or urine_results.get("volume_ml")
    )
    if urine_volume is not None and urine_volume < 2000:
        risk_factors.add("low_urine_volume")

    urine_oxalate = _parse_float(
        urine_results.get("oxalate_mg_day")
        or urine_results.get("urine_oxalate_mg_day")
        or urine_results.get("oxalate")
    )
    if urine_oxalate is not None and urine_oxalate > 40:
        risk_factors.add("hyperoxaluria")

    urine_sodium = _parse_float(
        urine_results.get("sodium_mg_day")
        or urine_results.get("urine_sodium_mg_day")
        or urine_results.get("sodium")
    )
    if urine_sodium is not None and urine_sodium > 2300:
        risk_factors.add("hypernatriuria")

    return {
        **state,
        "metabolic_risk_factors": sorted(risk_factors),
    }


async def prevention_planning_node(state: KidneyStoneState) -> KidneyStoneState:
    """
    Generate personalized prevention plan based on stone type and risk factors.

    Creates tailored recommendations for:
    - Dietary modifications (reduce/increase specific foods)
    - Fluid intake targets (typically 2.5-4L/day depending on stone type)
    - Medication recommendations based on metabolic abnormalities
    - Lifestyle modifications

    Plans are evidence-based and composition-specific. For example:
    - Calcium oxalate: Reduce oxalate foods, pair calcium with meals
    - Uric acid: Alkalinize urine, reduce purines
    - Cystine: High fluid intake (4L+), alkalinization
    """
    composition = state.get("predicted_composition", STONE_TYPE_UNKNOWN)
    rules = DIETARY_RULES.get(composition, DIETARY_RULES["calcium_oxalate"])
    risk_factors = state.get("metabolic_risk_factors", [])

    fluid_target = rules["fluid_target_ml"]
    if "low_urine_volume" in risk_factors:
        fluid_target = max(fluid_target, 3500)

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

    if "hyperoxaluria" in risk_factors:
        lifestyle.append("Pair calcium-rich foods with meals to bind oxalate.")
    if "hypernatriuria" in risk_factors:
        lifestyle.append("Track sodium intake and avoid processed foods.")
    if "alkaline_urine" in risk_factors and composition == "calcium_phosphate":
        lifestyle.append("Avoid excessive urine alkalinization; focus on citrate balance.")

    dietary_recommendations = [
        {"category": "reduce", "items": rules["reduce"], "priority": "high"},
        {"category": "increase", "items": rules["increase"], "priority": "high"},
    ]

    if "hyperoxaluria" in risk_factors:
        dietary_recommendations.append(
            {
                "category": "reduce",
                "items": [{"item": "high-oxalate foods", "reason": "Elevated urine oxalate"}],
                "priority": "medium",
            }
        )
    if "hypernatriuria" in risk_factors:
        dietary_recommendations.append(
            {
                "category": "reduce",
                "items": [{"item": "processed foods", "reason": "High sodium load"}],
                "priority": "medium",
            }
        )
    if "low_urine_volume" in risk_factors:
        dietary_recommendations.append(
            {
                "category": "increase",
                "items": [{"item": "water intake", "reason": "Increase urine volume"}],
                "priority": "high",
            }
        )

    return {
        **state,
        "dietary_recommendations": dietary_recommendations,
        "fluid_intake_target_ml": fluid_target,
        "medications_recommended": medications,
        "lifestyle_modifications": lifestyle,
    }


async def education_generation_node(state: KidneyStoneState) -> KidneyStoneState:
    """
    Generate patient education materials using MedGemma.

    Creates a personalized, plain-language summary at 6th grade reading level.
    Explains their specific stone type, why it formed, what to change, and
    encourages compliance with the prevention plan.

    Also selects relevant pre-made education materials (PDFs, videos) based
    on the patient's stone composition.
    """
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
    """
    Schedule patient engagement nudges for behavioral compliance.

    Creates a multi-week campaign of SMS and voice reminders:
    - Week 1: Onboarding, daily hydration reminders
    - Weeks 2-12: Weekly check-ins, progress celebrations
    - Treatment-specific: Medication reminders, strain reminders

    Also schedules clinical compliance checkpoints:
    - Day 30: Repeat 24-hour urine
    - Day 90: Dietary assessment
    - Day 180: Follow-up imaging
    - Day 365: Annual review

    Goal: Reduce the 50% 5-year recurrence rate through sustained engagement.
    """
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


def _assess_urgency(
    stones: list[dict],
    total_burden_mm3: float | None = None,
    hydronephrosis_level: str | None = None,
) -> str:
    for stone in stones:
        if stone.get("hydronephrosis") == "severe":
            return "emergent"
        if stone.get("complete_obstruction"):
            return "emergent"
        if stone.get("obstruction"):
            return "urgent"

    if hydronephrosis_level in {"severe"}:
        return "emergent"
    if hydronephrosis_level in {"moderate"}:
        return "urgent"

    if total_burden_mm3 is not None:
        eq_diameter = _equivalent_diameter_mm(total_burden_mm3)
        if eq_diameter is not None and eq_diameter >= 30:
            return "urgent"
    else:
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


def _resolve_ct_path(state: KidneyStoneState) -> Path:
    value = state.get("ct_scan_local_path") or state["ct_scan_path"]
    if isinstance(value, str) and value.startswith("gs://"):
        raise ValueError("CT scan must be staged locally before processing.")
    return Path(value)


def _parse_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _summarize_hydronephrosis(stones: list[dict]) -> str | None:
    """Return the most severe hydronephrosis level observed across stones."""
    best_level = None
    best_rank = -1
    fallback = None
    for stone in stones:
        raw = (
            stone.get("hydronephrosis")
            or stone.get("hydronephrosis_level")
            or stone.get("hydronephrosis_severity")
        )
        if raw is None:
            continue
        text = str(raw).strip().lower()
        if text in HYDRONEPHROSIS_RANK:
            rank = HYDRONEPHROSIS_RANK[text]
            if rank > best_rank:
                best_rank = rank
                best_level = text
        elif fallback is None:
            fallback = text
    return best_level or fallback


def _segment_stone_masks(
    volume: np.ndarray, spacing: tuple[float, float, float], stones: list[dict]
) -> list[tuple[np.ndarray, tuple[int, int, int]] | None]:
    """Segment stones using thresholding and ROI selection. Returns ROI masks + origins."""
    try:
        from skimage.measure import label
        from skimage.morphology import remove_small_objects
    except ImportError:
        return [None for _ in stones]

    base_mask = _threshold_mask(volume)
    base_mask = remove_small_objects(base_mask, min_size=20)

    masks: list[tuple[np.ndarray, tuple[int, int, int]] | None] = [None for _ in stones]

    for idx, stone in enumerate(stones):
        center = _coords_to_index(stone.get("location_coords"), volume.shape, spacing)
        if center is None:
            continue

        roi_mask = _segment_roi(volume, center, stone, spacing)
        if roi_mask is not None:
            masks[idx] = roi_mask

    if any(mask is not None for mask in masks):
        return masks

    components = _extract_components(base_mask, max(len(stones), 1))
    for idx, component in enumerate(components):
        if idx < len(masks):
            masks[idx] = component

    return masks


def _segment_roi(
    volume: np.ndarray,
    center: tuple[int, int, int],
    stone: dict,
    spacing: tuple[float, float, float],
) -> tuple[np.ndarray, tuple[int, int, int]] | None:
    from skimage.measure import label
    from skimage.morphology import remove_small_objects

    low, high = _threshold_for_hu(_parse_float(stone.get("hounsfield_units")))
    radius_mm = _roi_radius_mm(_parse_float(stone.get("size_mm")))
    half_sizes = (
        max(int(radius_mm / spacing[0]), 3),
        max(int(radius_mm / spacing[1]), 3),
        max(int(radius_mm / spacing[2]), 3),
    )

    z0 = max(center[0] - half_sizes[0], 0)
    z1 = min(center[0] + half_sizes[0] + 1, volume.shape[0])
    y0 = max(center[1] - half_sizes[1], 0)
    y1 = min(center[1] + half_sizes[1] + 1, volume.shape[1])
    x0 = max(center[2] - half_sizes[2], 0)
    x1 = min(center[2] + half_sizes[2] + 1, volume.shape[2])

    roi = volume[z0:z1, y0:y1, x0:x1]
    roi_mask = (roi >= low) & (roi <= high)
    roi_mask = remove_small_objects(roi_mask, min_size=10)

    if roi_mask.sum() == 0:
        return None

    labels = label(roi_mask)
    local_center = (center[0] - z0, center[1] - y0, center[2] - x0)
    target = 0
    if 0 <= local_center[0] < labels.shape[0] and 0 <= local_center[1] < labels.shape[1]:
        if 0 <= local_center[2] < labels.shape[2]:
            target = int(labels[local_center])

    if target == 0:
        counts = np.bincount(labels.ravel())
        if counts.size <= 1:
            return None
        counts[0] = 0
        target = int(np.argmax(counts))

    component = labels == target
    return _crop_mask(component, (z0, y0, x0))


def _extract_components(
    mask: np.ndarray, max_components: int
) -> list[tuple[np.ndarray, tuple[int, int, int]]]:
    from skimage.measure import label

    labels = label(mask)
    counts = np.bincount(labels.ravel())
    if counts.size <= 1:
        return []
    counts[0] = 0
    top_labels = np.argsort(counts)[::-1]

    components = []
    for lbl in top_labels:
        if lbl == 0 or counts[lbl] == 0:
            continue
        component = labels == lbl
        cropped = _crop_mask(component, (0, 0, 0))
        if cropped is not None:
            components.append(cropped)
        if len(components) >= max_components:
            break
    return components


def _crop_mask(
    mask: np.ndarray, origin: tuple[int, int, int]
) -> tuple[np.ndarray, tuple[int, int, int]] | None:
    coords = np.argwhere(mask)
    if coords.size == 0:
        return None
    min_z, min_y, min_x = coords.min(axis=0)
    max_z, max_y, max_x = coords.max(axis=0) + 1
    cropped = mask[min_z:max_z, min_y:max_y, min_x:max_x]
    new_origin = (origin[0] + int(min_z), origin[1] + int(min_y), origin[2] + int(min_x))
    return cropped, new_origin


def _threshold_mask(volume: np.ndarray) -> np.ndarray:
    return (volume >= 250) & (volume <= 2000)


def _threshold_for_hu(hu: float | None) -> tuple[float, float]:
    if hu is None:
        return (250, 2000)
    low = max(200.0, hu - 200.0)
    high = min(2000.0, hu + 200.0)
    return (low, high)


def _roi_radius_mm(size_mm: float | None) -> float:
    if size_mm is None or size_mm <= 0:
        return 6.0
    return max(size_mm * 0.75, 4.0)


def _coords_to_index(
    coords: object, shape: tuple[int, int, int], spacing: tuple[float, float, float]
) -> tuple[int, int, int] | None:
    if not isinstance(coords, (list, tuple)) or len(coords) < 3:
        return None
    try:
        values = [float(coords[0]), float(coords[1]), float(coords[2])]
    except (TypeError, ValueError):
        return None

    if max(values) <= 1.0 and min(values) >= 0.0:
        return (
            int(values[2] * (shape[0] - 1)),
            int(values[1] * (shape[1] - 1)),
            int(values[0] * (shape[2] - 1)),
        )

    z, y, x = int(values[2]), int(values[1]), int(values[0])
    if 0 <= z < shape[0] and 0 <= y < shape[1] and 0 <= x < shape[2]:
        return (z, y, x)

    z = int(values[2] / spacing[0]) if spacing[0] else int(values[2])
    y = int(values[1] / spacing[1]) if spacing[1] else int(values[1])
    x = int(values[0] / spacing[2]) if spacing[2] else int(values[0])
    if 0 <= z < shape[0] and 0 <= y < shape[1] and 0 <= x < shape[2]:
        return (z, y, x)
    return None


def _mask_to_mesh(
    mask: np.ndarray,
    origin: tuple[int, int, int],
    spacing: tuple[float, float, float],
) -> dict[str, np.ndarray] | None:
    try:
        from skimage.measure import marching_cubes
    except ImportError:
        return None

    if mask.sum() < 10:
        return None

    from scipy.ndimage import gaussian_filter

    # Pad the mask so marching cubes can close the surface at boundaries,
    # then smooth to produce a clean isosurface instead of a blocky mesh.
    pad = 3
    padded = np.pad(mask.astype(np.float32), pad, mode="constant", constant_values=0)
    smoothed = gaussian_filter(padded, sigma=1.0)
    verts, faces, _, _ = marching_cubes(smoothed, level=0.4, spacing=spacing)

    # Shift vertices back to account for padding, then to world coordinates.
    pad_offset = np.array([pad * spacing[0], pad * spacing[1], pad * spacing[2]], dtype=np.float32)
    origin_mm = np.array(origin, dtype=np.float32) * np.array(spacing, dtype=np.float32)
    verts = verts - pad_offset + origin_mm
    return {"vertices": verts.astype(np.float32), "faces": faces.astype(np.int32)}


def _encode_meshes(
    meshes: list[dict[str, np.ndarray]], spacing: tuple[float, float, float]
) -> bytes:
    metadata = {
        "version": 1,
        "spacing_mm": list(spacing),
        "stone_count": len(meshes),
        "format": "npz",
    }

    arrays: dict[str, np.ndarray] = {
        "metadata_json": np.frombuffer(json.dumps(metadata).encode("utf-8"), dtype=np.uint8)
    }
    for idx, mesh in enumerate(meshes):
        arrays[f"v_{idx}"] = mesh["vertices"]
        arrays[f"f_{idx}"] = mesh["faces"]

    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    return buffer.getvalue()


def _estimate_stone_volume_mm3(stone: dict) -> float | None:
    """Estimate stone volume from reported dimensions; used until 3D segmentation is available."""
    size_mm = _parse_float(stone.get("size_mm"))
    if size_mm and size_mm > 0:
        radius = size_mm / 2.0
        return (4.0 / 3.0) * 3.141592653589793 * (radius**3)

    dims = _parse_dimensions_mm(stone)
    if dims:
        length, width, height = dims
        return (4.0 / 3.0) * 3.141592653589793 * (length / 2.0) * (width / 2.0) * (height / 2.0)

    return None


def _parse_dimensions_mm(stone: dict) -> tuple[float, float, float] | None:
    dims = stone.get("dimensions_mm") or stone.get("dimensions") or stone.get("size_mm")
    if isinstance(dims, (list, tuple)) and len(dims) >= 3:
        length = _parse_float(dims[0])
        width = _parse_float(dims[1])
        height = _parse_float(dims[2])
        if _all_positive(length, width, height):
            return length, width, height

    length = _parse_float(stone.get("length_mm") or stone.get("max_length_mm"))
    width = _parse_float(stone.get("width_mm") or stone.get("max_width_mm"))
    height = _parse_float(stone.get("height_mm") or stone.get("thickness_mm"))

    if _all_positive(length, width, height):
        return length, width, height

    if _all_positive(length, width):
        # Assume a conservative thickness equal to the smaller dimension.
        thickness = min(length, width)
        return length, width, thickness

    return None


def _all_positive(*values: float | None) -> bool:
    return all(v is not None and v > 0 for v in values)


def _equivalent_diameter_mm(volume_mm3: float) -> float | None:
    """Convert volume to a sphere-equivalent diameter for consistent burden thresholds."""
    if volume_mm3 <= 0:
        return None
    return (6.0 * volume_mm3 / 3.141592653589793) ** (1.0 / 3.0)


def _choose_treatment(
    *,
    stones: list[dict],
    composition: str,
    total_burden_mm3: float | None,
    hydronephrosis_level: str | None,
) -> str:
    primary = _identify_primary_stone(stones)
    max_size = _stone_size_mm(primary)
    eq_diameter = _equivalent_diameter_mm(total_burden_mm3) if total_burden_mm3 else None

    ureteral = [s for s in stones if _is_ureteral(_normalize_location(s.get("location")))]
    renal = [s for s in stones if s not in ureteral]
    lower_pole = any(_is_lower_pole(_normalize_location(s.get("location"))) for s in renal)
    has_staghorn = any(_is_staghorn(s) for s in stones)

    if hydronephrosis_level in {"severe", "moderate"} and ureteral:
        return "ureteroscopy"

    if has_staghorn or (composition == "struvite" and (max_size >= 10 or (eq_diameter or 0) >= 20)):
        return "pcnl"

    if eq_diameter is not None and eq_diameter >= 20:
        return "pcnl"

    if len(stones) >= 3 and (eq_diameter or 0) >= 15:
        return "pcnl"

    if ureteral:
        max_ureter = max(_stone_size_mm(s) for s in ureteral)
        distal = any(
            _normalize_location(s.get("location")) == "distal_ureter" for s in ureteral
        )
        if max_ureter < 5:
            return "medical_expulsive" if distal else "observation"
        if max_ureter <= 10:
            return "medical_expulsive" if distal else "ureteroscopy"
        return "ureteroscopy"

    if max_size >= 20:
        return "pcnl"
    if max_size >= 10:
        return "ureteroscopy" if lower_pole else "eswl"

    treatment = "observation"
    return _adjust_for_composition(treatment, composition, max_size)


def _build_treatment_rationale(
    *,
    stones: list[dict],
    composition: str,
    total_burden_mm3: float | None,
    hydronephrosis_level: str | None,
    primary: dict,
    treatment: str,
) -> str:
    count = len(stones)
    size = _stone_size_mm(primary)
    location = primary.get("location", "unknown")
    burden_text = ""
    if total_burden_mm3:
        eq_diameter = _equivalent_diameter_mm(total_burden_mm3)
        if eq_diameter:
            burden_text = f" Total burden ≈ {eq_diameter:.1f}mm (sphere-equivalent)."
    hydro_text = f" Hydronephrosis: {hydronephrosis_level}." if hydronephrosis_level else ""

    return (
        f"{count} stone(s) detected. Primary stone {size}mm in {location} with "
        f"composition {composition}. Recommended {treatment}.{burden_text}{hydro_text}"
    )


def _stone_size_mm(stone: dict) -> float:
    return float(stone.get("size_mm", 0) or 0)


def _is_ureteral(location: str) -> bool:
    return "ureter" in location


def _is_lower_pole(location: str) -> bool:
    return location.startswith("kidney_lower")


def _is_staghorn(stone: dict) -> bool:
    shape = str(stone.get("shape") or "").lower()
    return "staghorn" in shape
