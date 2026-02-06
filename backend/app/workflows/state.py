from typing import Literal, Optional, TypedDict


class KidneyStoneState(TypedDict, total=False):
    patient_id: str
    provider_id: str

    ct_scan_path: str
    ct_scan_local_path: str
    stones_detected: list[dict]
    predicted_composition: str
    composition_confidence: float
    stone_3d_model: bytes | None
    total_stone_burden_mm3: float | None
    hydronephrosis_level: str | None

    treatment_recommendation: str
    treatment_rationale: str
    urgency_level: Literal["emergent", "urgent", "routine", "elective"]

    crystallography_results: Optional[dict]
    urine_24hr_results: Optional[dict]
    metabolic_risk_factors: list[str]

    dietary_recommendations: list[dict]
    fluid_intake_target_ml: int
    medications_recommended: list[dict]
    lifestyle_modifications: list[str]

    education_materials: list[dict]
    personalized_summary: str

    nudge_schedule: list[dict]
    compliance_checkpoints: list[dict]
