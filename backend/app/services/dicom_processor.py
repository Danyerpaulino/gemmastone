from pathlib import Path

import numpy as np
import pydicom
from pydicom.misc import is_dicom
from pydicom.pixel_data_handlers import apply_voi_lut


class DicomProcessor:
    @staticmethod
    def load_series(directory: Path) -> np.ndarray:
        directory = Path(directory)
        dcm_files = _collect_dicom_files(directory)
        if not dcm_files:
            raise FileNotFoundError(f"No DICOM files found in {directory}")

        slices = []
        for path in dcm_files:
            try:
                slices.append(pydicom.dcmread(path, force=True))
            except Exception:
                continue
        if not slices:
            raise FileNotFoundError(f"No readable DICOM slices found in {directory}")

        def sort_key(ds):
            if hasattr(ds, "ImagePositionPatient"):
                return float(ds.ImagePositionPatient[2])
            if hasattr(ds, "SliceLocation"):
                return float(ds.SliceLocation)
            if hasattr(ds, "InstanceNumber"):
                return int(ds.InstanceNumber)
            return 0

        slices.sort(key=sort_key)

        try:
            slice_arrays = [
                apply_voi_lut(ds.pixel_array, ds).astype(np.float32) for ds in slices
            ]
        except Exception as exc:
            raise RuntimeError(
                "Unable to decode DICOM pixel data. Ensure JPEG codecs are available "
                "(pylibjpeg + libjpeg/openjpeg) for compressed CTs."
            ) from exc

        if len(slice_arrays) == 1 and slice_arrays[0].ndim == 3:
            volume = slice_arrays[0]
        else:
            volume = np.stack(slice_arrays)

        slope = getattr(slices[0], "RescaleSlope", 1)
        intercept = getattr(slices[0], "RescaleIntercept", 0)
        volume = volume * slope + intercept

        return volume

    @staticmethod
    def get_spacing(directory: Path) -> tuple[float, float, float]:
        """Return (z, y, x) spacing in millimeters for the series."""
        directory = Path(directory)
        dcm_files = _collect_dicom_files(directory)
        if not dcm_files:
            raise FileNotFoundError(f"No DICOM files found in {directory}")

        first = pydicom.dcmread(dcm_files[0], stop_before_pixels=True, force=True)
        second = (
            pydicom.dcmread(dcm_files[1], stop_before_pixels=True, force=True)
            if len(dcm_files) > 1
            else None
        )

        pixel_spacing = getattr(first, "PixelSpacing", [1.0, 1.0])
        y_spacing = float(pixel_spacing[0]) if len(pixel_spacing) > 0 else 1.0
        x_spacing = float(pixel_spacing[1]) if len(pixel_spacing) > 1 else y_spacing

        z_spacing = getattr(first, "SliceThickness", None)
        if not z_spacing and second is not None:
            if hasattr(first, "ImagePositionPatient") and hasattr(second, "ImagePositionPatient"):
                z_spacing = abs(float(second.ImagePositionPatient[2]) - float(first.ImagePositionPatient[2]))

        return (float(z_spacing or 1.0), y_spacing, x_spacing)


def _collect_dicom_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]

    candidates = [p for p in path.rglob("*") if p.is_file()]
    dicoms = [p for p in candidates if _is_dicom_candidate(p)]

    if dicoms:
        return sorted(dicoms)

    # Fallback for extensionless DICOMs without a preamble.
    return sorted([p for p in candidates if _looks_like_dicom(p)])


def _is_dicom_candidate(path: Path) -> bool:
    if path.suffix.lower() in {".dcm", ".ima", ".dicom"}:
        return True
    try:
        return is_dicom(str(path))
    except Exception:
        return False


def _looks_like_dicom(path: Path) -> bool:
    try:
        pydicom.dcmread(path, stop_before_pixels=True, force=True)
        return True
    except Exception:
        return False
