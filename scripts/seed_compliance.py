from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path
import sys
from random import Random

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.db.models import ComplianceLog, Patient, PreventionPlan  # noqa: E402


def _get_latest_plan(db, patient_id):
    return (
        db.query(PreventionPlan)
        .filter(PreventionPlan.patient_id == patient_id)
        .order_by(PreventionPlan.created_at.desc())
        .first()
    )


def seed_compliance(
    patient_id: str,
    days: int = 14,
    clear: bool = False,
    seed: int = 42,
) -> dict:
    db = SessionLocal()
    try:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise SystemExit(f"Patient not found: {patient_id}")

        if clear:
            db.query(ComplianceLog).filter(
                ComplianceLog.patient_id == patient_id
            ).delete(synchronize_session=False)
            db.commit()

        plan = _get_latest_plan(db, patient_id)
        fluid_goal = plan.fluid_intake_target_ml if plan and plan.fluid_intake_target_ml else 2500

        rng = Random(seed)
        created = 0
        updated = 0

        for offset in range(days):
            log_date = date.today() - timedelta(days=offset)
            log = (
                db.query(ComplianceLog)
                .filter(
                    ComplianceLog.patient_id == patient_id,
                    ComplianceLog.log_date == log_date,
                )
                .first()
            )
            if not log:
                log = ComplianceLog(patient_id=patient_id, log_date=log_date)
                created += 1
            else:
                updated += 1

            base = fluid_goal + rng.randint(-400, 300)
            if offset % 6 == 0:
                base = int(fluid_goal * 0.7)
            if offset % 10 == 0:
                base = None

            log.fluid_intake_ml = base if base is None else max(base, 0)
            log.medication_taken = None if offset % 5 == 0 else (offset % 2 == 0)
            log.dietary_compliance_score = None if offset % 7 == 0 else round(
                rng.uniform(0.6, 0.95), 2
            )
            log.notes = "Seeded demo log"

            db.add(log)

        db.commit()

        return {
            "patient_id": patient_id,
            "days": days,
            "fluid_goal": fluid_goal,
            "created": created,
            "updated": updated,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed mock compliance logs")
    parser.add_argument("--patient-id", required=True, help="Patient UUID")
    parser.add_argument("--days", type=int, default=14, help="Number of days to seed")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete existing logs for the patient before seeding",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic mock values",
    )
    args = parser.parse_args()

    result = seed_compliance(
        patient_id=args.patient_id,
        days=args.days,
        clear=args.clear,
        seed=args.seed,
    )

    print("Seeded compliance logs:")
    for key, value in result.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
