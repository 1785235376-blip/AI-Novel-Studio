"""Upscale adapter contract on the existing ImageJob/Asset/review pipeline.

The former reservation remains readable for old callers. Execution uses an
explicit Model Center registration and the closed Comfy upscale recipe.
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


ImageUpscaleInput = ReservedImageUpscaleInput


class ImageUpscaleAdapter(Protocol):
    """Fixed provider entry points used by the original execution owner."""
    def image_recipe(self, request: AssetGenerationRequest, *, operation: str,
                     reference_weights: tuple, mask: bool,
                     source_dimensions: dict | None = None) -> dict: ...

    def generate_image(self, request: AssetGenerationRequest, *, operation: str,
                       images: list[str], reference_weights: list[float],
                       mask: str | None = None) -> AssetGenerationResult: ...


def reservation():
    return {"contract": "studio-image-upscale-reservation/1", "status": "NOT_CONFIGURED",
        "execution_available": False, "automatic_download": False,
        "owner": "ImageJobService", "output_policy": "PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW",
        "product_acceptance": "LOCAL_REQUIRED"}


def execution_contract():
    return {"contract": "studio-image-upscale-execution/1", "status": "IMPLEMENTED",
        "operation_id": "m5.image.upscale", "recipe_id": "comfy-upscale-model-v1",
        "scales": [2, 4], "output_format": "PNG", "automatic_download": False,
        "provider_policy": "EXPLICIT_ENABLED_LOCAL_MODEL_CENTER_REGISTRATION",
        "owner": "ImageJobService", "output_policy": "PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW",
        "product_acceptance": "LOCAL_REQUIRED"}
