"""Host-local discovery inputs. Neither discovery nor validation can execute a process."""
from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LOCAL_TYPES = Literal['OLLAMA', 'LLAMA_CPP', 'COMFYUI', 'AUTOMATIC1111', 'OPENAI_COMPATIBLE_LOCAL', 'CUSTOM_HTTP']
MODALITIES = Literal['TEXT', 'VISION', 'IMAGE', 'VIDEO', 'AUDIO', 'TTS', 'RESTORATION', 'INTERPOLATION', 'UNKNOWN']


def local_endpoint(value: str) -> str:
    """Canonical numeric loopback, no DNS, proxy, credentials, query or fragment."""
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ''
        if host.lower() == 'localhost':
            host = '127.0.0.1'
        address = ipaddress.ip_address(host)
        if (not address.is_loopback or parsed.scheme not in {'http', 'https'} or
                parsed.username is not None or parsed.password is not None or
                parsed.query or parsed.fragment or parsed.port is None or '%' in host or
                '\\' in value or any(ord(c) < 32 for c in value)):
            raise ValueError()
        netloc = f'[{host}]:{parsed.port}' if address.version == 6 else f'{host}:{parsed.port}'
        path = parsed.path.rstrip('/')
        if '%' in path or '..' in path.split('/'):
            raise ValueError()
        return urlunsplit((parsed.scheme, netloc, path, '', ''))
    except (ValueError, TypeError) as exc:
        raise ValueError('LOCAL_AI_LOOPBACK_ENDPOINT_REQUIRED') from exc


def safe_local_path(value: str) -> str:
    if not value:
        return ''
    if value.startswith(('\\\\', '//')):
        raise ValueError('LOCAL_AI_NETWORK_PATH_REJECTED')
    path = Path(value).expanduser()
    if not path.is_absolute() or path == Path(path.anchor):
        raise ValueError('LOCAL_AI_SCOPED_ABSOLUTE_PATH_REQUIRED')
    # No linked roots, junctions, or links in ancestors. Do not follow them first.
    for part in (path, *path.parents):
        try: reparse = getattr(part.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400
        except FileNotFoundError: reparse = 0
        except OSError as exc: raise ValueError('LOCAL_AI_PATH_UNREADABLE') from exc
        if part.is_symlink() or reparse or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('LOCAL_AI_LINKED_PATH_REJECTED')
    if __import__('os').name == 'nt':
        import ctypes
        if ctypes.windll.kernel32.GetDriveTypeW(str(path.anchor)) == 4:
            raise ValueError('LOCAL_AI_NETWORK_PATH_REJECTED')
    return str(path.resolve(strict=False))


class LocalRuntimeInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    type: LOCAL_TYPES
    endpoint: str = Field(max_length=500)
    model_id: str = Field(default='', max_length=256)
    modality: MODALITIES = 'UNKNOWN'
    health_endpoint: str = Field(default='', max_length=100)
    credential_required: bool = False
    management: Literal['EXTERNAL', 'MANAGED'] = 'EXTERNAL'
    executable: str = Field(default='', max_length=2048)
    model_path: str = Field(default='', max_length=2048)
    context_size: int = Field(default=8192, ge=512, le=131072)
    gpu_layers: int = Field(default=0, ge=0, le=999)
    threads: int | None = Field(default=None, ge=1, le=512)
    batch_size: int | None = Field(default=None, ge=1, le=4096)

    _endpoint = field_validator('endpoint')(local_endpoint)
    _paths = field_validator('executable', 'model_path')(safe_local_path)

    @field_validator('health_endpoint')
    @classmethod
    def health(cls, value: str) -> str:
        if value and (not value.startswith('/') or value.startswith('//') or any(c in value for c in '?%#\\') or '..' in value.split('/')):
            raise ValueError('LOCAL_AI_HEALTH_PATH_INVALID')
        return value

    @model_validator(mode='after')
    def managed(self):
        if self.management == 'MANAGED' and self.type != 'LLAMA_CPP':
            raise ValueError('LOCAL_AI_EXTERNAL_RUNTIME_REQUIRED')
        return self


class DiscoverySettingsInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scan_roots: list[str] = Field(default_factory=list, max_length=16)
    include_common_model_dirs: bool = True

    @field_validator('scan_roots')
    @classmethod
    def roots(cls, values: list[str]):
        return list(dict.fromkeys(safe_local_path(value) for value in values if value))


class EnableInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmed: Literal[True]

    @field_validator('confirmed', mode='before')
    @classmethod
    def explicit_boolean(cls, value):
        if value is not True: raise ValueError('LOCAL_AI_EXPLICIT_CONFIRMATION_REQUIRED')
        return value


class RegistrationInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    workflow_adapter_id: str = Field(default='', max_length=100)
    license_confirmed: bool = False


class HardwareComponentEvidence(BaseModel):
    """A passive component hint never certifies driver usability or inference."""
    model_config = ConfigDict(extra='forbid')
    status: Literal['NOT_RUN', 'NOT_FOUND', 'COMPONENT_FOUND_NOT_VERIFIED', 'NOT_VERIFIED'] = 'NOT_RUN'
    source: str = 'NOT_RUN'
    inference_verified: Literal[False] = False


class EnvironmentGpu(BaseModel):
    model_config = ConfigDict(extra='forbid')
    vendor: str = 'UNKNOWN'
    name: str = 'NOT_VERIFIED'
    dedicated_vram_bytes: int | None = Field(default=None, ge=0)


class EnvironmentHardware(BaseModel):
    model_config = ConfigDict(extra='ignore')
    platform: str = 'UNKNOWN'
    architecture: str = 'UNKNOWN'
    cpu: str = 'NOT_VERIFIED'
    logical_cpu_count: int | None = Field(default=None, ge=1)
    ram_bytes: int | None = Field(default=None, ge=0)
    gpus: list[EnvironmentGpu] = Field(default_factory=list)
    status: str = 'NOT_VERIFIED'
    notes: list[str] = Field(default_factory=list)
    cuda: HardwareComponentEvidence = Field(default_factory=HardwareComponentEvidence)
    directml: HardwareComponentEvidence = Field(default_factory=HardwareComponentEvidence)


class EnvironmentService(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    name: str
    type: str
    endpoint: str
    status: str
    version: str | None = None
    notes: list[str] = Field(default_factory=list)
    available_models: list[str] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)
    inference_verified: Literal[False] = False


class EnvironmentModelFile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    path: str
    name: str
    format: Literal['GGUF', 'SAFETENSORS', 'DIFFUSERS']
    source: Literal['CONFIGURED', 'COMMON']
    root: str
    size_bytes: int = Field(ge=0)
    modified_ns: int
    header_valid: bool
    family: str = 'UNKNOWN'
    declared_capabilities: list[str] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    inference_verified: Literal[False] = False


class EnvironmentScanRoot(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str
    source: Literal['CONFIGURED', 'COMMON']
    status: Literal['PENDING', 'SCANNED', 'NOT_FOUND', 'UNREADABLE', 'REJECTED', 'BOUNDED', 'CANCELLED'] = 'PENDING'


class EnvironmentError(BaseModel):
    model_config = ConfigDict(extra='ignore')
    code: str
    runtime_id: str | None = None
    root: str | None = None


class EnvironmentScanLimits(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scan_budget_seconds: int = 45
    request_timeout_seconds: float = 2.0
    max_services: int = 20
    max_models_per_service: int = 512
    max_response_bytes: int = 4 * 1024 * 1024
    max_roots: int = 32
    max_entries: int = 5000
    max_files: int = 2000
    max_depth: int = 3
    max_metadata_bytes: int = 256 * 1024


class AIEnvironmentReport(BaseModel):
    """Host-session-only display contract; cannot serve as routing authority."""
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[2] = 2
    execution_scope: Literal['BACKEND_HOST'] = 'BACKEND_HOST'
    inference_status: Literal['NOT_RUN'] = 'NOT_RUN'
    windows_acceptance: Literal['NOT_RUN'] = 'NOT_RUN'
    scan_id: str | None = None
    status: Literal['NOT_SCANNED', 'RUNNING', 'COMPLETED', 'PARTIAL', 'CANCELLED'] = 'NOT_SCANNED'
    started_at: str | None = None
    finished_at: str | None = None
    hardware: EnvironmentHardware = Field(default_factory=EnvironmentHardware)
    services: list[EnvironmentService] = Field(default_factory=list)
    model_files: list[EnvironmentModelFile] = Field(default_factory=list)
    roots: list[EnvironmentScanRoot] = Field(default_factory=list)
    errors: list[EnvironmentError] = Field(default_factory=list)
    limits: EnvironmentScanLimits = Field(default_factory=EnvironmentScanLimits)
    notes: list[str] = Field(default_factory=lambda: ['BACKEND_HOST_ONLY', 'NO_MODEL_LOADED', 'NO_INFERENCE_RUN', 'WINDOWS_NATIVE_ACCEPTANCE_NOT_RUN'])
