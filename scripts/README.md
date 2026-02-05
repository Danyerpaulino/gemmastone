# Scripts

## seed_demo.py
Seeds a demo provider, patient, and lab results. Optionally uploads a CT and runs `/ct/analyze`.

Examples:
- `python scripts/seed_demo.py` (generates a synthetic CT and runs `/ct/analyze`)
- `python scripts/seed_demo.py --ct-path ./data/sample_ct.zip --api-url http://localhost:8080/api`
