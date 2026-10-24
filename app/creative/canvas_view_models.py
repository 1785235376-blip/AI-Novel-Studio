"""Independent display views under the existing Creative Graph owner.

These records never describe execution ports, edges, jobs or model authority.
"""
from typing import Literal
from pydantic import Field, model_validator, field_validator, model_serializer
from .graph_models import Strict, Id, RequestId, Position, Viewport, AssetParameters
from .production_execution_models import CanvasImageNodeBinding

CANVAS_VIEWS = 'creative_canvas_views_v2'
MAX_CANVAS_VIEWS = 8
MAX_CANVAS_CARDS = 1000
MAX_CANVAS_DEFINITION_BYTES = 512_000

class CanvasAssetCard(Strict):
    id: Id
    position: Position
    asset: AssetParameters

class CanvasDisplayGroup(Strict):
    id: Id
    name: str = Field(min_length=1, max_length=80, strict=True)
    card_ids: list[Id] = Field(default_factory=list, max_length=MAX_CANVAS_CARDS, strict=True)
    parent_id: Id | None = None
    collapsed: bool = Field(default=False, strict=True)

    @model_serializer(mode='wrap')
    def absent_parent(self, handler):
        value = handler(self)
        if self.parent_id is None: value.pop('parent_id', None)
        return value

    @model_validator(mode='after')
    def unique_members(self):
        if not self.name.strip() or len(set(self.card_ids)) != len(self.card_ids):
            raise ValueError('CREATIVE_CANVAS_GROUP_INVALID')
        return self

class CanvasViewOptions(Strict):
    grid: bool = Field(strict=True)
    snap_step: Literal[8, 16, 24, 32] | None

    @field_validator('snap_step', mode='before')
    @classmethod
    def exact_step(cls, value):
        if value is not None and (type(value) is not int or value not in (8, 16, 24, 32)):
            raise ValueError('CREATIVE_CANVAS_SNAP_INVALID')
        return value

class CanvasImageNodeOrigin(Strict):
    contract: Literal['studio-canvas-image-node-result/1']
    target: CanvasImageNodeBinding
    job_id: str = Field(min_length=1, max_length=240, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$')
    job_version: int = Field(ge=1, le=2**53 - 1, strict=True)
    job_request_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    asset: AssetParameters

    @model_validator(mode='after')
    def image_only(self):
        if self.asset.kind != 'image':
            raise ValueError('CREATIVE_CANVAS_IMAGE_NODE_IMAGE_REQUIRED')
        return self


class CanvasViewDefinition(Strict):
    schema_version: Literal[1] = 1
    title: str = Field(min_length=1,max_length=160)
    cards: list[CanvasAssetCard] = Field(default_factory=list,max_length=MAX_CANVAS_CARDS)
    viewport: Viewport = Field(default_factory=Viewport)
    groups: list[CanvasDisplayGroup] | None = Field(default=None, min_length=1, max_length=64, strict=True)

    view_options: CanvasViewOptions | None = None
    image_node_origin: CanvasImageNodeOrigin | None = None

    @model_serializer(mode='wrap')
    def preserve_legacy_definition(self, handler):
        value = handler(self)
        if self.groups is None: value.pop('groups', None)
        if self.view_options is None: value.pop('view_options', None)
        if self.image_node_origin is None: value.pop('image_node_origin', None)
        return value

    @model_validator(mode='before')
    @classmethod
    def absent_not_null(cls, value):
        if isinstance(value, dict) and 'groups' in value and value['groups'] is None:
            raise ValueError('CREATIVE_CANVAS_GROUP_INVALID')
        if isinstance(value, dict) and 'view_options' in value and value['view_options'] is None:
            raise ValueError('CREATIVE_CANVAS_OPTIONS_INVALID')
        if isinstance(value, dict) and 'image_node_origin' in value and value['image_node_origin'] is None:
            raise ValueError('CREATIVE_CANVAS_IMAGE_NODE_ORIGIN_INVALID')
        return value


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
        if self.image_node_origin is not None:
            card = next((card for card in self.cards if card.id == self.image_node_origin.target.node_id), None)
            if card is None or card.asset != self.image_node_origin.asset:
                raise ValueError('CREATIVE_CANVAS_IMAGE_NODE_PIN_CHANGED')
        groups = {group.id: group for group in self.groups or []}
        if len(groups) != len(self.groups or []):
            raise ValueError('CREATIVE_CANVAS_GROUP_ID_INVALID')
        cards = {card.id for card in self.cards}; members = set()
        for group in groups.values():
            if any(member not in cards or member in members for member in group.card_ids):
                raise ValueError('CREATIVE_CANVAS_GROUP_MEMBER_INVALID')
            members.update(group.card_ids)
            seen = {group.id}; parent_id = group.parent_id
            while parent_id is not None:
                if parent_id not in groups or parent_id in seen or len(seen) >= 8:
                    raise ValueError('CREATIVE_CANVAS_GROUP_PARENT_INVALID')
                seen.add(parent_id); parent_id = groups[parent_id].parent_id
        if len(canonical(self.model_dump()).encode('utf-8')) > MAX_CANVAS_DEFINITION_BYTES:
            raise ValueError('CREATIVE_CANVAS_DEFINITION_CAPACITY')
        return self

class CanvasViewCreate(Strict):
    request_id: RequestId
    expected_version: int = Field(default=0,ge=0,le=0,strict=True)
    definition: CanvasViewDefinition

class CanvasCardPin(Strict):
    card_id: Id
    source: AssetParameters

class CanvasViewSave(Strict):
    expected_version: int = Field(ge=1,strict=True)
    definition: CanvasViewDefinition
    expected_incarnation: str | None = Field(default=None, min_length=1, max_length=240, strict=True)
    expected_definition_digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$', strict=True)
    expected_card: CanvasCardPin | None = None

    @model_validator(mode='after')
    def paired_origin_fence(self):
        supplied = self.model_fields_set & {'expected_incarnation', 'expected_definition_digest'}
        if supplied and (len(supplied) != 2 or self.expected_incarnation is None or self.expected_definition_digest is None):
            raise ValueError('CREATIVE_CANVAS_SAVE_ORIGIN_FENCE_INVALID')
        if 'expected_card' in self.model_fields_set and (self.expected_card is None or len(supplied) != 2):
            raise ValueError('CREATIVE_CANVAS_SAVE_CARD_FENCE_INVALID')
        return self

    @model_serializer(mode='wrap')
    def legacy_save_identity(self, handler):
        value = handler(self)
        if self.expected_incarnation is None:
            value.pop('expected_incarnation', None); value.pop('expected_definition_digest', None)
        if self.expected_card is None: value.pop('expected_card', None)
        return value

class CanvasViewRestore(Strict):
    expected_version: int = Field(ge=1, strict=True)
    expected_definition_digest: str = Field(pattern=r'^[a-f0-9]{64}$', strict=True)
    expected_incarnation: str = Field(min_length=1, max_length=240, strict=True)
    restore_version: int = Field(ge=1, strict=True)
    restore_definition_digest: str = Field(pattern=r'^[a-f0-9]{64}$', strict=True)


class CanvasImageNodeResult(Strict):
    confirmed: Literal[True]
    expected_incarnation: str = Field(min_length=1, max_length=240, strict=True)
    expected_version: int = Field(ge=1, le=2**53 - 1, strict=True)
    expected_definition_digest: str = Field(pattern=r'^[a-f0-9]{64}$', strict=True)
    job_id: str = Field(min_length=1, max_length=240, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$')
    job_version: int = Field(ge=1, le=2**53 - 1, strict=True)
    job_request_digest: str = Field(pattern=r'^[a-f0-9]{64}$', strict=True)
    asset: AssetParameters

    @field_validator('confirmed', mode='before')
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError('CREATIVE_CANVAS_IMAGE_NODE_CONFIRMATION_REQUIRED')
        return value
