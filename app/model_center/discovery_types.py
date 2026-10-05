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
