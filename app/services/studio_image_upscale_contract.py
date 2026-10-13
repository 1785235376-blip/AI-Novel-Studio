"""Non-executable upscale extension contract; no owner, route or model loader.

An eventual implementation must delegate to the existing ImageJob/Asset/review
pipeline. This request is deliberately not part of MediaOperation or Graph.
"""
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, model_validator

from ..creative.production_contracts import ProductionSourceSnapshot
from ..asset_providers import AssetGenerationRequest, AssetGenerationResult


class ReservedImageUpscaleInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source: ProductionSourceSnapshot
    scale: Literal[2, 4]
    output_format: Literal["PNG"] = "PNG"

    @model_validator(mode="after")
    def original_image(self):
        if self.source.kind != "ASSET" or self.source.asset_kind != "image":
            raise ValueError("STUDIO_IMAGE_UPSCALE_SOURCE_INVALID")
        return self


class ReservedImageUpscaleAdapter(Protocol):
    def upscale(self, request: AssetGenerationRequest, *, source_image: str,
                parameters: ReservedImageUpscaleInput) -> AssetGenerationResult: ...


def reservation():
    return {"contract": "studio-image-upscale-reservation/1", "status": "NOT_CONFIGURED",
        "execution_available": False, "automatic_download": False,
        "owner": "ImageJobService", "output_policy": "PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW",
        "product_acceptance": "LOCAL_REQUIRED"}
