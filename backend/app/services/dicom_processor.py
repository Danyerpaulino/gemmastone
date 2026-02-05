from pathlib import Path

import numpy as np
import pydicom
from pydicom.pixel_data_handlers import apply_voi_lut


class DicomProcessor:
    @staticmethod
    def load_series(directory: Path) -> np.ndarray:
        directory = Path(directory)
        if directory.is_file():
            directory = directory.parent

        dcm_files = sorted(directory.glob("*.dcm"))
        if not dcm_files:
            raise FileNotFoundError(f"No DICOM files found in {directory}")

        slices = [pydicom.dcmread(path) for path in dcm_files]

        def sort_key(ds):
            if hasattr(ds, "ImagePositionPatient"):
                return float(ds.ImagePositionPatient[2])
            if hasattr(ds, "SliceLocation"):
                return float(ds.SliceLocation)
            if hasattr(ds, "InstanceNumber"):
                return int(ds.InstanceNumber)
            return 0

        slices.sort(key=sort_key)

        volume = np.stack(
            [apply_voi_lut(ds.pixel_array, ds).astype(np.float32) for ds in slices]
        )

        slope = getattr(slices[0], "RescaleSlope", 1)
        intercept = getattr(slices[0], "RescaleIntercept", 0)
        volume = volume * slope + intercept

        return volume
