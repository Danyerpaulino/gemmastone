from typing import Any

from pydantic import BaseModel, Field


class StoneMesh(BaseModel):
    vertices: list[list[float]]
    faces: list[list[int]]


class MeshResponse(BaseModel):
    available: bool
    metadata: dict[str, Any] | None = None
    meshes: list[StoneMesh] = Field(default_factory=list)
