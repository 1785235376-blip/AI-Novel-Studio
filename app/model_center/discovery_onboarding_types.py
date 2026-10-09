"""Closed consent input; a digest is a scope receipt, never an access credential."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, field_validator


class ScanScopeConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scope_digest: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("LOCAL_AI_EXPLICIT_CONFIRMATION_REQUIRED")
        return value


class ScopeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ScanScopeService(ScopeModel):
    id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=40)
    endpoint: str = Field(max_length=500)
    management: Literal["EXTERNAL", "MANAGED"]
    probe_paths: list[str] = Field(max_length=16)


class ScanScopeRoot(ScopeModel):
    path: str = Field(min_length=1, max_length=2048)
    source: Literal["CONFIGURED", "COMMON"]


class ScanMetadataInspection(ScopeModel):
    kind: str = Field(pattern=r"^[A-Z_]{1,80}$")
    path: str = Field(min_length=1, max_length=2048)
    max_entries: int = Field(ge=0, le=5000)
    max_bytes: int = Field(ge=0, le=1048576)


class ScanScopeEffects(ScopeModel):
    launches: Literal[False]
    loads_weights: Literal[False]
    registers: Literal[False]
    enables: Literal[False]
    cloud_calls: Literal[False]
    persists_settings: Literal[False]
    may_disable_stale_registrations: Literal[True]
    persists_registration_safety_updates: Literal[True]


class ScanScopePreview(ScopeModel):
    schema_version: Literal[1]
    execution_scope: Literal["BACKEND_HOST"]
    scope_digest: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    include_common_model_dirs: bool
    services: list[ScanScopeService] = Field(max_length=20)
    roots: list[ScanScopeRoot] = Field(max_length=32)
    metadata_inspections: list[ScanMetadataInspection] = Field(max_length=2200)
    hardware_categories: list[str] = Field(max_length=16)
    limits: dict[str, Annotated[StrictInt | StrictFloat, Field(ge=0)]] = Field(max_length=32)
    inference_status: Literal["NOT_RUN"]
    requires_confirmation: Literal[True]
    side_effects: ScanScopeEffects
