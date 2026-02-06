# Architecture notes

## Stone modeling notes (current)

We estimate stone burden as a stopgap until true 3D segmentation is wired.
This is used for demo readiness and workflow completeness, not clinical use.

## Stone modeling notes (segmentation + mesh)

We run a lightweight segmentation step to produce a coarse 3D mesh and
calculate stone burden in mm³. This favors speed and demo robustness.

### Segmentation approach
- Threshold CT volume by HU range (default 250–2000).
- If stone coordinates are available, perform ROI thresholding around the
  coordinate and keep the connected component that contains the seed (or
  the largest component in that ROI).
- If no coordinates are available, use global thresholding and take the
  largest connected components (up to the number of detected stones).
- Small components are removed to reduce noise.

### CT output normalization
- MedGemma output is validated against a lightweight schema.
- Size values are normalized to millimeters using DICOM spacing.
- Supported inputs include `size_mm`, `size_voxels/size_px`, `dimensions_*`,
  and `bbox_*` (z_min,y_min,x_min,z_max,y_max,x_max).

## Treatment + prevention logic (current)

Treatment recommendations use a multi-factor ruleset:
- Primary driver: stone size, location, and total burden.
- Modifiers: hydronephrosis/obstruction, staghorn pattern, and struvite risk.
- Ureteral stones favor MET/URS based on size and distal/proximal location.

Prevention planning incorporates lab-derived risk factors when available:
- Low urine volume → higher fluid targets.
- Hyperoxaluria/hypernatriuria → targeted diet reductions.
- Urine pH extremes → citrate or alkalinization guidance as appropriate.

### Mesh output
- Each stone mask is converted to a surface using marching cubes.
- Meshes are stored as a compressed NPZ blob containing:
  - `metadata_json` (UTF-8 JSON as uint8 array)
  - `v_{i}` vertices and `f_{i}` faces for each stone

### Fall back
If segmentation fails (missing dependency or empty mask), we fall back to
the size-based volume estimate described below.

### Burden estimation (approximate)
- If `size_mm` is available, approximate a sphere volume:
  - `V = (4/3) * pi * (d/2)^3`
- If 3D dimensions are available (`length/width/height`), approximate an ellipsoid:
  - `V = (4/3) * pi * (L/2) * (W/2) * (H/2)`
- If only length + width exist, use the smaller value as a conservative thickness.

### Threshold normalization
When volume is available, we convert to an equivalent sphere diameter for
consistent thresholds:
`d_eq = (6V/pi)^(1/3)`
- Current urgency rule flags "urgent" at `d_eq >= 30mm` (aligned with prior sum-of-sizes heuristic).

### Planned upgrade
Replace the approximation with CT segmentation + mesh generation and compute
volume directly from the 3D mask.

## Human-in-the-loop + engagement gating
- Nudges are held until provider approval; campaigns start as `pending_approval`.
- Dispatcher checks provider approval and patient contact preferences before sending.
- Inbound SMS/voice responses update daily compliance logs for hydration/medication.

## Lab-driven re-run path
- When new labs are submitted for an analysis, we re-run lab integration, treatment,
  prevention, education, and nudge scheduling without reprocessing the CT.
- This yields a new active prevention plan and a new pending-approval campaign.
