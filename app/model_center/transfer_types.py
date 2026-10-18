"""Closed, host-reviewed single-artifact transfer inputs; no public catalog import."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal

MAX_ARTIFACT_BYTES = 64 * 1024**3
TRANSFER_STATES = frozenset({'TRANSFERRING', 'PAUSING', 'PAUSED', 'VERIFYING',
    'CANCELLING', 'COMPLETED', 'CANCELLED', 'FAILED', 'INTERRUPTED', 'CLEANED'})
ACTIVE_STATES = frozenset({'TRANSFERRING', 'PAUSING', 'VERIFYING', 'CANCELLING'})


class TransferError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class ClosedInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)


def reviewed_https_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment
                or parsed.port not in (None, 443) or '\\' in value
                or any(ord(c) <= 32 or ord(c) >= 127 for c in value)
                or '%' in value or '..' in parsed.path.split('/')):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('MODEL_TRANSFER_SOURCE_INVALID') from None
    return value


class ReviewedTransferSource(ClosedInput):
    """Only trusted Host composition may construct these; none ship by default.

    A structurally valid record is not proof of publisher or license review.
    Host composition must supply independently reviewed evidence, never copy
    historical model metadata or accept a browser-supplied record as authority.
    """
    id: str = Field(pattern=r'^[a-z0-9][a-z0-9-]{0,79}$')
    model_id: str = Field(min_length=1, max_length=160)
    display_name: str = Field(min_length=1, max_length=160)
    publisher: str = Field(min_length=1, max_length=160)
    license_name: str = Field(min_length=1, max_length=160)
    license_url: str = Field(min_length=1, max_length=2048)
    model_card_url: str = Field(min_length=1, max_length=2048)
    url: str = Field(min_length=1, max_length=2048)
    revision: str = Field(min_length=1, max_length=160)
    size_bytes: int = Field(ge=8, le=MAX_ARTIFACT_BYTES)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')

    _https = field_validator('url', 'license_url', 'model_card_url')(reviewed_https_url)

    @field_validator('model_id', 'display_name', 'publisher', 'license_name', 'revision')
    @classmethod
    def bounded_text(cls, value):
        if value != value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError('MODEL_TRANSFER_SOURCE_INVALID')
        return value

    @field_validator('url')
    @classmethod
    def gguf_only(cls, value):
        if not urlsplit(value).path.endswith('.gguf'):
            raise ValueError('MODEL_TRANSFER_GGUF_REQUIRED')
        return value


class PreviewInput(ClosedInput):
    source_id: str = Field(pattern=r'^[a-z0-9][a-z0-9-]{0,79}$')


class ConfirmationInput(ClosedInput):
    preview_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirmed: Literal[True]

    @field_validator('confirmed', mode='before')
    @classmethod
    def literal_confirmation(cls, value):
        if value is not True:
            raise ValueError('MODEL_TRANSFER_CONFIRMATION_REQUIRED')
        return value


class VersionInput(ClosedInput):
    expected_version: int = Field(ge=1, le=2**53 - 1)


class ResumeInput(VersionInput):
    confirmed: Literal[True]
    _confirmed = field_validator('confirmed', mode='before')(ConfirmationInput.literal_confirmation.__func__)


class CleanupInput(ConfirmationInput):
    expected_version: int = Field(ge=1, le=2**53 - 1)


def task_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value):
        raise TransferError('MODEL_TRANSFER_NOT_FOUND')
    return value
