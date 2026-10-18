"""Independent display views under the existing Creative Graph owner.

These records never describe execution ports, edges, jobs or model authority.
"""
from typing import Literal
from pydantic import Field, model_validator, field_validator
from .graph_models import Strict, Id, RequestId, Position, Viewport, AssetParameters

CANVAS_VIEWS = 'creative_canvas_views_v2'
MAX_CANVAS_VIEWS = 8
MAX_CANVAS_CARDS = 1000
MAX_CANVAS_DEFINITION_BYTES = 512_000

class CanvasAssetCard(Strict):
    id: Id
    position: Position
    asset: AssetParameters

class CanvasViewDefinition(Strict):
    schema_version: Literal[1] = 1
    title: str = Field(min_length=1,max_length=160)
    cards: list[CanvasAssetCard] = Field(default_factory=list,max_length=MAX_CANVAS_CARDS)
    viewport: Viewport = Field(default_factory=Viewport)

    @field_validator('schema_version', mode='before')
    @classmethod
    def exact_schema(cls,value):
        if type(value) is not int or value != 1:raise ValueError('CREATIVE_CANVAS_SCHEMA_INVALID')
        return value

    @model_validator(mode='after')
    def bounded(self):
        from ..experimental.store import canonical
        if not self.title.strip() or len({card.id for card in self.cards}) != len(self.cards):
            raise ValueError('CREATIVE_CANVAS_CARD_ID_OR_TITLE_INVALID')
        if len(canonical(self.model_dump()).encode('utf-8')) > MAX_CANVAS_DEFINITION_BYTES:
            raise ValueError('CREATIVE_CANVAS_DEFINITION_CAPACITY')
        return self

class CanvasViewCreate(Strict):
    request_id: RequestId
    expected_version: int = Field(default=0,ge=0,le=0,strict=True)
    definition: CanvasViewDefinition

class CanvasViewSave(Strict):
    expected_version: int = Field(ge=1,strict=True)
    definition: CanvasViewDefinition
