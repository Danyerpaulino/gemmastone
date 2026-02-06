from __future__ import annotations

import argparse
from datetime import date
import os
from pathlib import Path
import sys
import tempfile
import zipfile

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.db.models import LabResult, Patient, Provider  # noqa: E402


def seed_demo(
    provider_email: str,
    provider_name: str,
    patient_first: str,
    patient_last: str,
    patient_email: str,
) -> dict:
    db = SessionLocal()
    try:
        provider = (
            db.query(Provider).filter(Provider.email == provider_email).first()
        )
        if not provider:
            provider = Provider(
                email=provider_email,
                name=provider_name,
                specialty="Urology",
                practice_name="KidneyStone AI Clinic",
            )
            db.add(provider)
            db.commit()
            db.refresh(provider)

        patient = None
        if patient_email:
            patient = (
                db.query(Patient).filter(Patient.email == patient_email).first()
            )
        if not patient:
            patient = Patient(
                provider_id=provider.id,
                first_name=patient_first,
                last_name=patient_last,
                email=patient_email,
                phone="+15555550123",
                mrn="DEMO-0001",
            )
            db.add(patient)
            db.commit()
            db.refresh(patient)

        cryst = LabResult(
            patient_id=patient.id,
            result_type="crystallography",
            result_date=date.today(),
            results={
                "composition": "calcium_oxalate",
                "notes": "Calcium oxalate monohydrate predominant",
            },
        )
        urine = LabResult(
            patient_id=patient.id,
            result_type="urine_24hr",
            result_date=date.today(),
            results={
                "volume_ml_day": 1700,
                "calcium_mg_day": 320,
                "citrate_mg_day": 250,
                "uric_acid_mg_day": 820,
                "ph": 5.3,
                "sodium_mg_day": 2400,
            },
        )
        db.add_all([cryst, urine])
        db.commit()
        db.refresh(cryst)
        db.refresh(urine)

        return {
            "provider_id": str(provider.id),
            "patient_id": str(patient.id),
            "crystallography_lab_id": str(cryst.id),
            "urine_24hr_lab_id": str(urine.id),
        }
    finally:
        db.close()


def _zip_ct_dir(ct_dir: Path) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()
    zip_path = Path(tmp.name)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in ct_dir.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(ct_dir))
    return zip_path


def _create_synthetic_ct(ct_dir: Path, slices: int = 8, size: int = 128) -> Path:
    import numpy as np
    import pydicom
    from datetime import datetime
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

    ct_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.utcnow()

    study_uid = generate_uid()
    series_uid = generate_uid()

    for index in range(slices):
        pixel = np.random.normal(loc=30, scale=5, size=(size, size)).astype(np.int16)
        rr, cc = np.ogrid[:size, :size]
        center = size // 2 + (index - slices // 2)
        mask = (rr - center) ** 2 + (cc - center) ** 2 <= (size // 10) ** 2
        pixel[mask] = 1200

        file_meta = FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = CTImageStorage
        file_meta.MediaStorageSOPInstanceUID = generate_uid()
        file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

        ds = FileDataset(
            str(ct_dir / f"slice_{index + 1:03d}.dcm"),
            {},
            file_meta=file_meta,
            preamble=b"\0" * 128,
        )
        ds.is_little_endian = True
        ds.is_implicit_VR = False

        ds.Modality = "CT"
        ds.ContentDate = now.strftime("%Y%m%d")
        ds.ContentTime = now.strftime("%H%M%S")
        ds.PatientName = "SYNTHETIC^DEMO"
        ds.PatientID = "DEMO-CT"
        ds.StudyInstanceUID = study_uid
        ds.SeriesInstanceUID = series_uid
        ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
        ds.SOPClassUID = file_meta.MediaStorageSOPClassUID

        ds.Rows, ds.Columns = pixel.shape
        ds.PixelSpacing = [1.0, 1.0]
        ds.SliceThickness = 1.0
        ds.ImagePositionPatient = [0.0, 0.0, float(index)]
        ds.InstanceNumber = index + 1

        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.BitsStored = 16
        ds.BitsAllocated = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 1
        ds.RescaleIntercept = -1024
        ds.RescaleSlope = 1
        ds.PixelData = pixel.tobytes()

        ds.save_as(ds.filename)

    return ct_dir


def run_ct_analysis(
    api_url: str,
    ct_path: Path,
    provider_id: str,
    patient_id: str,
    api_token: str | None = None,
) -> dict:
    api_url = api_url.rstrip("/")
    upload_path = ct_path
    cleanup_zip = False
    if ct_path.is_dir():
        upload_path = _zip_ct_dir(ct_path)
        cleanup_zip = True

    try:
        with upload_path.open("rb") as handle:
            content_type = "application/zip" if upload_path.suffix.lower() == ".zip" else "application/octet-stream"
            files = {"file": (upload_path.name, handle, content_type)}
            data = {"patient_id": patient_id, "provider_id": provider_id}
            headers = {}
            if api_token:
                headers["Authorization"] = f"Bearer {api_token}"
            response = httpx.post(
                f"{api_url}/ct/analyze",
                files=files,
                data=data,
                headers=headers,
                timeout=300,
            )
            if not response.is_success:
                detail = response.text
                raise SystemExit(
                    f"/ct/analyze failed ({response.status_code}). Response: {detail}"
                )
            return response.json()
    finally:
        if cleanup_zip and upload_path.exists():
            upload_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo provider/patient/labs")
    parser.add_argument("--provider-email", default="demo.provider@kidneystone.ai")
    parser.add_argument("--provider-name", default="Dr. Demo Provider")
    parser.add_argument("--patient-first", default="Jamie")
    parser.add_argument("--patient-last", default="Stone")
    parser.add_argument("--patient-email", default="demo.patient@kidneystone.ai")
    parser.add_argument("--api-url", default="http://localhost:8080/api")
    parser.add_argument("--api-token", default=None)
    parser.add_argument(
        "--ct-path",
        help="Path to CT DICOM directory or .zip file. If omitted, a synthetic CT is generated.",
    )
    args = parser.parse_args()

    ids = seed_demo(
        provider_email=args.provider_email,
        provider_name=args.provider_name,
        patient_first=args.patient_first,
        patient_last=args.patient_last,
        patient_email=args.patient_email,
    )

    print("Seeded demo data:")
    for key, value in ids.items():
        print(f"- {key}: {value}")

    ct_path = None
    temp_dir = None
    if args.ct_path:
        ct_path = Path(args.ct_path)
        if not ct_path.exists():
            raise SystemExit(f"CT path not found: {ct_path}")
    else:
        temp_dir = tempfile.TemporaryDirectory()
        ct_path = _create_synthetic_ct(Path(temp_dir.name) / "synthetic_ct")
        print(f"Generated synthetic CT at: {ct_path}")

    api_token = args.api_token or os.getenv("API_TOKEN")
    print("Running /ct/analyze...")
    result = run_ct_analysis(
        args.api_url,
        ct_path,
        ids["provider_id"],
        ids["patient_id"],
        api_token=api_token,
    )
    analysis_id = result.get("analysis", {}).get("id")
    print(f"Analysis complete. analysis_id={analysis_id}")

    if temp_dir:
        temp_dir.cleanup()


if __name__ == "__main__":
    main()
