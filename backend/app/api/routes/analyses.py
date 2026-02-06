import io
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

import numpy as np

from app.crud import analysis as analysis_crud
from app.crud import lab_result as lab_crud
from app.db.models import Patient, Provider
from app.db.session import get_db
from app.schemas.analysis import (
    StoneAnalysisCreate,
    StoneAnalysisPublic,
    StoneAnalysisPublicList,
)
from app.schemas.lab_result import LabResultOut
from app.schemas.mesh import MeshResponse

router = APIRouter()


@router.post("/", response_model=StoneAnalysisPublic, status_code=201)
def create_analysis(
    payload: StoneAnalysisCreate,
    db: Session = Depends(get_db),
) -> StoneAnalysisPublic:
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=400, detail="Patient does not exist")

    provider = db.query(Provider).filter(Provider.id == payload.provider_id).first()
    if not provider:
        raise HTTPException(status_code=400, detail="Provider does not exist")

    analysis = analysis_crud.create_analysis(db, payload)
    return StoneAnalysisPublic.model_validate(analysis)


@router.get("/", response_model=StoneAnalysisPublicList)
def list_analyses(
    offset: int = 0,
    limit: int = 100,
    patient_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> StoneAnalysisPublicList:
    items = analysis_crud.list_analyses(db, offset=offset, limit=limit, patient_id=patient_id)
    total = analysis_crud.count_analyses(db, patient_id=patient_id)
    public_items = [StoneAnalysisPublic.model_validate(item) for item in items]
    return StoneAnalysisPublicList(items=public_items, total=total)


@router.get("/{analysis_id}", response_model=StoneAnalysisPublic)
def get_analysis(
    analysis_id: UUID,
    db: Session = Depends(get_db),
) -> StoneAnalysisPublic:
    analysis = analysis_crud.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    labs = lab_crud.list_lab_results(db, analysis_id=analysis_id, limit=500)
    analysis_out = StoneAnalysisPublic.model_validate(analysis).model_copy(
        update={"lab_results": [LabResultOut.model_validate(lab) for lab in labs]}
    )
    return analysis_out


@router.get("/{analysis_id}/mesh", response_model=MeshResponse)
def get_analysis_mesh(
    analysis_id: UUID,
    db: Session = Depends(get_db),
) -> MeshResponse:
    analysis = analysis_crud.get_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if not analysis.stone_3d_model:
        return MeshResponse(available=False, metadata=None, meshes=[])

    try:
        decoded = _decode_mesh_blob(analysis.stone_3d_model)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to decode stone mesh: {exc}") from exc

    return MeshResponse(
        available=True,
        metadata=decoded.get("metadata"),
        meshes=decoded.get("meshes", []),
    )


def _decode_mesh_blob(blob: bytes | memoryview) -> dict:
    raw = bytes(blob)
    meshes: list[dict] = []
    metadata: dict = {}

    with np.load(io.BytesIO(raw), allow_pickle=False) as data:
        if "metadata_json" in data:
            try:
                metadata = json.loads(bytes(data["metadata_json"]).decode("utf-8"))
            except json.JSONDecodeError:
                metadata = {}

        idx = 0
        while True:
            v_key = f"v_{idx}"
            f_key = f"f_{idx}"
            if v_key not in data or f_key not in data:
                break
            vertices = data[v_key].astype(float).tolist()
            faces = data[f_key].astype(int).tolist()
            meshes.append({"vertices": vertices, "faces": faces})
            idx += 1

    return {"metadata": metadata, "meshes": meshes}
