from __future__ import annotations

from typing import Any


COMPOSITION_KEYS = (
    "composition",
    "stone_type",
    "stone_composition",
    "primary_composition",
)

URINE_REQUIRED_KEYS = (
    "volume_ml_day",
    "calcium_mg_day",
    "citrate_mg_day",
    "ph",
)

URINE_RANGES = {
    "volume_ml_day": (500, 10000),
    "calcium_mg_day": (0, 600),
    "citrate_mg_day": (0, 2000),
    "uric_acid_mg_day": (0, 1500),
    "ph": (4.5, 8.0),
    "sodium_mg_day": (0, 10000),
}


def validate_lab_results(result_type: str, results: dict[str, Any]) -> None:
    normalized = _normalize_result_type(result_type)
    if normalized == "crystallography":
        _validate_crystallography(results)
    elif normalized == "urine_24hr":
        _validate_urine(results)


def _normalize_result_type(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip().lower().replace("-", "_").replace(" ", "_")
    if "crystal" in text:
        return "crystallography"
    if "urine" in text and ("24" in text or "24hr" in text or "24h" in text):
        return "urine_24hr"
    return text


def _validate_crystallography(results: dict[str, Any]) -> None:
    if not isinstance(results, dict):
        raise ValueError("Crystallography results must be a JSON object.")

    for key in COMPOSITION_KEYS:
        value = results.get(key)
        if isinstance(value, str) and value.strip():
            return
    raise ValueError(
        "Crystallography results must include a non-empty composition field (composition/stone_type)."
    )


def _validate_urine(results: dict[str, Any]) -> None:
    if not isinstance(results, dict):
        raise ValueError("24hr urine results must be a JSON object.")

    missing = [key for key in URINE_REQUIRED_KEYS if results.get(key) is None]
    if missing:
        raise ValueError(f"24hr urine results missing required keys: {', '.join(missing)}")

    for key, (low, high) in URINE_RANGES.items():
        if key not in results or results.get(key) is None:
            continue
        value = _parse_float(results.get(key), key)
        if value < low or value > high:
            raise ValueError(f"{key} must be between {low} and {high}")


def _parse_float(value: Any, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
