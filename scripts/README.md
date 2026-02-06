# Scripts

## seed_demo.py
Seeds a demo provider, patient, and lab results. Optionally uploads a CT and runs `/ct/analyze`.

Examples:
- `python scripts/seed_demo.py` (generates a synthetic CT and runs `/ct/analyze`)
- `python scripts/seed_demo.py --ct-path ./data/sample_ct.zip --api-url http://localhost:8080/api`
- `python scripts/seed_demo.py --api-url https://<cloud-run>/api --api-token <API_TOKEN>`
  - Or set `API_TOKEN` in the environment instead of passing `--api-token`

## seed_compliance.py
Seeds mock compliance logs for a patient so the progress view has live data.

Examples:
- `python scripts/seed_compliance.py --patient-id <PATIENT_UUID>`
- `python scripts/seed_compliance.py --patient-id <PATIENT_UUID> --days 30 --clear`
