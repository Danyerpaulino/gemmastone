"""CT analysis output normalization and schema validation."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CTStone(BaseModel):
    model_config = ConfigDict(extra="allow")

    location: str | None = None
    location_coords: list[float] | None = None
    size_mm: float | None = None
    size_voxels: float | None = None
    dimensions_mm: list[float] | None = None
    dimensions_voxels: list[float] | None = None
    bbox_voxels: list[float] | None = None
    hounsfield_units: float | None = None
    shape: str | None = None
    hydronephrosis: str | None = None


class CTAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    stones: list[CTStone] = Field(default_factory=list)
    confidence: float | None = None
    predicted_composition: str | None = None


def normalize_ct_output(raw: Any, spacing: tuple[float, float, float]) -> tuple[list[dict], dict]:
    payload = _coerce_payload(raw)

    stones_raw = payload.get("stones")
    if stones_raw is None:
        stones_raw = payload.get("stones_detected")
    if stones_raw is None:
        stones_raw = payload.get("findings")

    if isinstance(stones_raw, dict):
        stones_raw = [stones_raw]
    if not isinstance(stones_raw, list):
        stones_raw = []

    normalized_stones: list[dict] = []
    for item in stones_raw:
        if not isinstance(item, dict):
            continue
        # Pre-process fields that may come as dicts but should be floats/lists
        item = _preprocess_stone_fields(item)
        stone_model = CTStone.model_validate(item)
        stone = {**item, **stone_model.model_dump(exclude_none=True)}
        normalized_stones.append(_normalize_stone_fields(stone, spacing))

    normalized_output = CTAnalysisOutput(
        stones=[CTStone.model_validate(stone) for stone in normalized_stones],
        confidence=_parse_float(payload.get("confidence")),
        predicted_composition=payload.get("predicted_composition"),
    )

    return normalized_stones, normalized_output.model_dump(exclude_none=True)


def _coords_dict_to_list(coords_dict: dict) -> list[float] | None:
    """Convert coordinate dict to [x, y, z] list."""
    try:
        # Try x, y, z keys
        if all(k in coords_dict for k in ("x", "y", "z")):
            return [
                float(coords_dict["x"]),
                float(coords_dict["y"]),
                float(coords_dict["z"]),
            ]
        # Try X, Y, Z keys (uppercase)
        if all(k in coords_dict for k in ("X", "Y", "Z")):
            return [
                float(coords_dict["X"]),
                float(coords_dict["Y"]),
                float(coords_dict["Z"]),
            ]
        return None
    except (TypeError, ValueError, KeyError):
        return None


def _preprocess_stone_fields(stone: dict) -> dict:
    """Convert fields that arrive as dicts to proper types before validation."""
    result = dict(stone)

    # Handle location_coords/location_coordinates as dict {"x": ..., "y": ..., "z": ...}
    # Must be converted BEFORE Pydantic validation since CTStone expects list
    for key in ("location_coords", "location_coordinates", "coords", "coordinates", "center_coords", "centroid"):
        value = result.get(key)
        if isinstance(value, dict):
            coords = _coords_dict_to_list(value)
            if coords:
                result["location_coords"] = coords
                # Remove the original dict key if it's not location_coords
                if key != "location_coords":
                    result.pop(key, None)
            else:
                # Remove invalid dict to prevent validation error
                result.pop(key, None)
            break

    # Handle size_voxels coming as a bounding box dict
    size_voxels = result.get("size_voxels")
    if isinstance(size_voxels, dict):
        # Extract bbox and compute max dimension, or remove for later normalization
        bbox = _bbox_dict_to_list(size_voxels)
        if bbox:
            result["bbox_voxels"] = bbox
        result.pop("size_voxels", None)

    # Handle dimensions_voxels as a bounding box dict
    dims_voxels = result.get("dimensions_voxels")
    if isinstance(dims_voxels, dict):
        bbox = _bbox_dict_to_list(dims_voxels)
        if bbox:
            result["bbox_voxels"] = bbox
        result.pop("dimensions_voxels", None)

    # Handle bbox_voxels as a dict
    bbox_voxels = result.get("bbox_voxels")
    if isinstance(bbox_voxels, dict):
        bbox = _bbox_dict_to_list(bbox_voxels)
        if bbox:
            result["bbox_voxels"] = bbox
        else:
            result.pop("bbox_voxels", None)

    return result


def _bbox_dict_to_list(bbox_dict: dict) -> list[float] | None:
    """Convert a bounding box dict to [x_min, y_min, z_min, x_max, y_max, z_max] list."""
    try:
        # Try standard min/max keys
        if all(k in bbox_dict for k in ("x_min", "y_min", "z_min", "x_max", "y_max", "z_max")):
            return [
                float(bbox_dict["x_min"]),
                float(bbox_dict["y_min"]),
                float(bbox_dict["z_min"]),
                float(bbox_dict["x_max"]),
                float(bbox_dict["y_max"]),
                float(bbox_dict["z_max"]),
            ]
        # Try just min/max (might be missing x/y/z prefix)
        if all(k in bbox_dict for k in ("min", "max")):
            min_val = bbox_dict["min"]
            max_val = bbox_dict["max"]
            if isinstance(min_val, (list, tuple)) and isinstance(max_val, (list, tuple)):
                return [float(v) for v in min_val[:3]] + [float(v) for v in max_val[:3]]
        return None
    except (TypeError, ValueError, KeyError):
        return None


def _coerce_payload(raw: Any) -> dict:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, list):
        if raw and isinstance(raw[0], dict):
            if "stones" in raw[0] or "stones_detected" in raw[0]:
                return dict(raw[0])
            return {"stones": raw}
    if isinstance(raw, str):
        text = raw.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return _coerce_payload(parsed)
    return {}


def _normalize_stone_fields(
    stone: dict, spacing: tuple[float, float, float]
) -> dict:
    normalized = dict(stone)
    normalized = _normalize_location_coords(normalized)
    normalized = _normalize_hounsfield(normalized)
    normalized = _normalize_sizes(normalized, spacing)
    return normalized


def _normalize_location_coords(stone: dict) -> dict:
    if "location_coords" in stone:
        return stone
    for key in (
        "coords",
        "coordinates",
        "location_coordinates",
        "center_coords",
        "centroid",
    ):
        if key in stone:
            value = stone[key]
            if isinstance(value, (list, tuple)):
                stone["location_coords"] = [float(v) for v in value[:3]]
                break
            elif isinstance(value, dict):
                # Handle dict-style coordinates like {"x": 150, "y": 150, "z": 100}
                coords = _coords_dict_to_list(value)
                if coords:
                    stone["location_coords"] = coords
                break
    return stone


def _normalize_hounsfield(stone: dict) -> dict:
    hu = stone.get("hounsfield_units")
    if hu is None:
        hu = stone.get("hu")
    parsed = _parse_float(hu)
    if parsed is not None:
        stone["hounsfield_units"] = parsed
    return stone


def _normalize_sizes(stone: dict, spacing: tuple[float, float, float]) -> dict:
    size_mm = _parse_float(
        _first_value(
            stone,
            "size_mm",
            "diameter_mm",
            "max_diameter_mm",
            "max_dimension_mm",
        )
    )

    dims_mm = _parse_vector(
        _first_value(stone, "dimensions_mm", "dims_mm", "dimensions")
    )

    if dims_mm:
        stone["dimensions_mm"] = dims_mm

    if size_mm is None and dims_mm:
        size_mm = max(dims_mm)

    if size_mm is None:
        size_voxels = _parse_float(
            _first_value(
                stone,
                "size_voxels",
                "size_px",
                "max_dimension_voxels",
                "max_dimension_px",
            )
        )
        if size_voxels:
            size_mm = size_voxels * max(spacing)

    if size_mm is None:
        dims_vox = _parse_vector(
            _first_value(
                stone,
                "dimensions_voxels",
                "dimensions_px",
                "dims_voxels",
                "dims_px",
            )
        )
        if dims_vox:
            dims_mm = _voxels_to_mm(dims_vox, spacing)
            stone["dimensions_mm"] = dims_mm
            size_mm = max(dims_mm)

    if size_mm is None:
        bbox_vox = _parse_vector(
            _first_value(
                stone,
                "bbox_voxels",
                "bbox_px",
                "bounding_box_voxels",
                "bounding_box_px",
                "bbox",
            )
        )
        if bbox_vox and len(bbox_vox) >= 6:
            dims_vox = [bbox_vox[3] - bbox_vox[0], bbox_vox[4] - bbox_vox[1], bbox_vox[5] - bbox_vox[2]]
            dims_mm = _voxels_to_mm(dims_vox, spacing)
            stone["dimensions_mm"] = dims_mm
            size_mm = max(dims_mm)

    if size_mm is not None:
        stone["size_mm"] = size_mm

    return stone


def _voxels_to_mm(dims_vox: list[float], spacing: tuple[float, float, float]) -> list[float]:
    if len(dims_vox) < 3:
        return [dims_vox[0] * max(spacing)]
    return [dims_vox[0] * spacing[0], dims_vox[1] * spacing[1], dims_vox[2] * spacing[2]]


def _first_value(stone: dict, *keys: str) -> Any:
    for key in keys:
        if key in stone and stone[key] is not None:
            return stone[key]
    return None


def _parse_vector(value: Any) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                return None
    if isinstance(value, (list, tuple)):
        parsed = [_parse_float(v) for v in value]
        if any(v is None for v in parsed):
            return None
        return [float(v) for v in parsed]
    return None


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
