"""Credential-free provider profile contracts, not a credential management API.

No runtime write route/UI is exposed until an OS-vault profile registrar and
per-project authority integration are implemented and verified. A reference is
an opaque vault entry UUID; plaintext keys/tokens are never accepted here.
"""
from __future__ import annotations
from typing import Literal, Protocol
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class VaultReference(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    backend: Literal['windows', 'keyring']
    entry_id: UUID


class ProviderProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    profile_id: UUID
    display_name: str = Field(min_length=1, max_length=120)
    provider_id: str = Field(pattern=r'^[a-z0-9][a-z0-9._-]{0,79}$')
    vault_reference: VaultReference
    enabled: bool = True
    revoked: bool = False
    model_ids: list[str] = Field(default_factory=list, max_length=100)
    capabilities: list[Literal['TEXT', 'IMAGE', 'VIDEO', 'AUDIO', 'EMBEDDING']] = Field(default_factory=list, max_length=5)

    @model_validator(mode='after')
    def revoked_profiles_are_disabled(self):
        if self.revoked and self.enabled:
            raise ValueError('revoked provider profile must be disabled')
        return self

    def public(self):
        # Vault location/entry identifiers do not belong in browser state.
        return {key: value for key, value in self.model_dump(mode='json').items() if key != 'vault_reference'} | {
            'credential_display': 'Stored in OS vault', 'secret': None,
            'configuration_status': 'HOST_INTEGRATION_REQUIRED',
        }


class ProviderProfileSelection(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    default_profile_id: UUID | None = None
    project_profile_ids: dict[str, UUID] = Field(default_factory=dict, max_length=10000)

    def select(self, novel_id: str, profiles: list[ProviderProfile], capability: str):
        selected = self.project_profile_ids.get(novel_id, self.default_profile_id)
        if selected is None:
            raise ValueError('PROVIDER_PROFILE_NOT_CONFIGURED')
        profile = next((row for row in profiles if row.profile_id == selected), None)
        if profile is None or not profile.enabled or profile.revoked or capability not in profile.capabilities:
            raise ValueError('PROVIDER_PROFILE_UNAVAILABLE')
        return profile


class OsVaultProfileRegistrar(Protocol):
    """Host-owned registration/revocation with required user confirmation.

    Implementations must keep entry/secret I/O on the OS vault boundary; this
    contract deliberately has no plaintext secret parameter or return value.
    """
    def reference_exists(self, reference: VaultReference) -> bool: ...
    def request_registration(self, provider_id: str) -> VaultReference: ...
    def request_revocation(self, reference: VaultReference) -> None: ...
