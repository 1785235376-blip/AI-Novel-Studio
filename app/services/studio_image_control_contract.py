"""Typed model-agnostic Control adapter reservation, without dispatch authority.

Control maps remain exact references to the original Asset owner. Neither this
protocol nor metadata discovery may select, download or run a control model.
"""
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..creative.production_contracts import ProductionSourceSnapshot

ControlKind = Literal["DEPTH", "POSE", "EDGE", "MASK", "LAYOUT"]


class ImageControlInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    kind: ControlKind
    source: ProductionSourceSnapshot
    weight: float = Field(gt=0, le=1)
    source_note: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def exact_original_asset(self):
        if self.source.kind != "ASSET" or self.source.asset_kind != "image":
            raise ValueError("STUDIO_IMAGE_CONTROL_SOURCE_INVALID")
        return self


class ImageControlAdapter(Protocol):
    def validate_control(self, value: ImageControlInput) -> ImageControlInput: ...


def reservation():
    return {"contract": "studio-image-control-reservation/1", "status": "NOT_CONFIGURED",
        "kinds": ["DEPTH", "POSE", "EDGE", "MASK", "LAYOUT"], "execution_available": False,
        "automatic_download": False, "owner": "ImageJobService",
        "source_policy": "EXACT_ASSET_VERSION_DIGEST", "product_acceptance": "LOCAL_REQUIRED"}
