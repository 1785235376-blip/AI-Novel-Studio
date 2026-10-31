"""Optional multimodal rules on the original STYLE authority, never a store."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

Dimension = Literal['writing_tone', 'camera_language', 'composition', 'color',
                    'linework_halftone', 'character_design', 'sound', 'music_theme']
DIMENSIONS = ('writing_tone', 'camera_language', 'composition', 'color',
              'linework_halftone', 'character_design', 'sound', 'music_theme')
Identifier = Annotated[str, Field(min_length=1, max_length=240, strict=True)]
Text = Annotated[str, Field(min_length=1, max_length=2000, strict=True)]

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

class SourcePin(Strict):
    id: Identifier
    version: int = Field(ge=1, strict=True)
    digest: str = Field(pattern=r'^[a-f0-9]{64}$', strict=True)

class StyleTarget(Strict):
    level: Literal['GLOBAL', 'CHAPTER', 'SCENE', 'SHOT']
    chapter: SourcePin | None = None
    document: SourcePin | None = None
    scene_id: Identifier | None = None
    shot_id: Identifier | None = None

    @model_validator(mode='after')
    def shape(self):
        actual = (self.chapter is not None, self.document is not None,
                  self.scene_id is not None, self.shot_id is not None)
        expected = {'GLOBAL': (False, False, False, False), 'CHAPTER': (True, False, False, False),
                    'SCENE': (False, True, True, False), 'SHOT': (False, True, True, True)}
        if actual != expected[self.level]:
            raise ValueError('STYLE_DNA_TARGET_SHAPE_INVALID')
        return self

    def key(self):
        return (self.level, self.chapter.id if self.chapter else None,
                self.document.id if self.document else None, self.scene_id, self.shot_id)

class StyleOverride(Strict):
    target: StyleTarget
    rules: dict[Dimension, Text] = Field(min_length=1, max_length=8)

    @model_validator(mode='after')
    def local_only(self):
        if self.target.level == 'GLOBAL' or any(not v.strip() for v in self.rules.values()):
            raise ValueError('STYLE_DNA_OVERRIDE_INVALID')
        return self

class StyleDNA(Strict):
    schema_version: Literal[1] = 1
    global_rules: dict[Dimension, Text] = Field(default_factory=dict, max_length=8)
    overrides: list[StyleOverride] = Field(default_factory=list, max_length=50)

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_schema(cls, value):
        if type(value) is not int:
            raise ValueError("STYLE_DNA_SCHEMA_INVALID")
        return value

    @model_validator(mode='after')
    def rules(self):
        if not self.global_rules and not self.overrides:
            raise ValueError('STYLE_DNA_RULES_REQUIRED')
        if any(not v.strip() for v in self.global_rules.values()):
            raise ValueError('STYLE_DNA_RULE_EMPTY')
        if len({item.target.key() for item in self.overrides}) != len(self.overrides):
            raise ValueError('STYLE_DNA_DUPLICATE_TARGET')
        return self

class StyleResolutionIn(Strict):
    expected_version: int = Field(ge=1, strict=True)
    expected_digest: str = Field(pattern=r'^[a-f0-9]{64}$', strict=True)
    target: StyleTarget
