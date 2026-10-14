"""Strict request contracts for the unified production workflow projection.

Only the neutral studio's own creative intent is mutable here. Intent and preset
remain presentation hints: they grant no authorization, select no asset kind and
authorize no execution. The original project, asset, job and timeline owners are
read, never replaced.
"""
from pydantic import Field

from ..experimental.media import StrictModel

# Fixed integration order of the unified production workflow. The projection
# always returns exactly these modules in exactly this order.
PRODUCTION_WORKFLOW_MODULES = ("director", "storyboard", "image", "video", "audio", "timeline", "asset")

MAX_INTENT_VALUES = 11


class ProductionIntentValue(StrictModel):
    intent_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    label: str = Field(min_length=1, max_length=120)
    selected: bool


class ProductionIntentUpdate(StrictModel):
    """Replace the saved neutral intent set with one explicit, versioned value.

    ``expected_version`` is mandatory lossless optimistic concurrency. ``None``
    declares "no intent has been saved yet" and fails closed when a row exists,
    so an unread client can never silently overwrite a saved intent.
    """

    expected_version: int | None = Field(default=None, ge=0, le=2**53 - 1, strict=True)
    values: list[ProductionIntentValue] = Field(default_factory=list, max_length=MAX_INTENT_VALUES)
    preset: str | None = Field(default=None, min_length=1, max_length=32)
