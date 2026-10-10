from __future__ import annotations

import os
import base64
import ipaddress
from urllib.parse import urlsplit
from dataclasses import dataclass, field
from typing import Any, Protocol

from .audio_provider_config import load as load_audio_provider_config


AUDIO_PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "dasheng-local": {
        "display_name": "Dasheng-AudioGen（本地）",
        "endpoint": "http://127.0.0.1:8001/v1",
        "default_model": "dasheng-audiogen",
        "local": True,
        "requires_credential": False,
        "capabilities": ["TEXT_TO_AUDIO", "TTS"],
        "license": "Apache-2.0",
        "priority": 10,
    },
    "stable-audio-local": {
        "display_name": "Stable Audio 3 Medium（本地）",
        "endpoint": "http://127.0.0.1:8002/v1",
        "default_model": "stable-audio-3-medium",
        "local": True,
        "requires_credential": False,
        "capabilities": ["TEXT_TO_AUDIO", "AUDIO_EDIT", "SFX", "FOLEY", "MUSIC"],
        "priority": 20,
    },
    "mmaudio-local": {
        "display_name": "MMAudio（本地）",
        "endpoint": "http://127.0.0.1:8003/v1",
        "default_model": "mmaudio",
        "local": True,
        "requires_credential": False,
        "capabilities": ["VIDEO_TO_AUDIO", "SFX", "FOLEY"],
        "priority": 30,
    },
    "aliyun-bailian": {
        "display_name": "阿里云百炼",
        "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "cosyvoice-v3-flash",
        "local": False,
        "requires_credential": True,
        "capabilities": ["TTS"],
        "priority": 100,
    },
    "siliconflow": {
        "display_name": "硅基流动",
        "endpoint": "https://api.siliconflow.cn/v1",
        "default_model": "FunAudioLLM/CosyVoice2-0.5B",
        "local": False,
        "requires_credential": True,
        "capabilities": ["TTS"],
        "priority": 110,
    },
    "minimax": {
        "display_name": "MiniMax",
        "endpoint": "https://api.minimax.chat/v1",
        "default_model": "speech-02-hd",
        "local": False,
        "requires_credential": True,
        "capabilities": ["TTS"],
        "priority": 120,
    },
    "openai": {
        "display_name": "OpenAI",
        "endpoint": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini-tts",
        "local": False,
        "requires_credential": True,
        "capabilities": ["TTS"],
        "priority": 200,
    },
}


@dataclass(frozen=True)
class AudioGenerationRequest:
    provider_id: str
    model_id: str
    capability: str
    prompt: str
    task_id: str
    voice: str | None = None
    source_audio_uri: str | None = None
    source_video_uri: str | None = None
    duration_seconds: float | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AudioGenerationResult:
    provider_id: str
    model_id: str
    audio_uri: str
    remote_task_id: str | None = None
    status: str = "SUCCEEDED"


class AudioProvider(Protocol):
    def generate(self, request: AudioGenerationRequest) -> AudioGenerationResult: ...
    def health_check(self) -> bool: ...


class HttpAudioProvider:
    """Adapter for local or cloud audio services exposing the studio HTTP contract."""

    def __init__(self, transport, endpoint: str, api_key: str | None = None, *, local: bool = False, emotion_values: tuple[str, ...] = ()):
        if not endpoint:
            raise ValueError("audio provider endpoint is required")
        self.transport = transport
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.local = bool(local)
        self.emotion_values = emotion_values

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def health_check(self) -> bool:
        try:
            return 200 <= self.transport.get(self.endpoint + "/models", headers=self._headers(), timeout=1.5).status_code < 300
        except Exception:
            return False

    def generate(self, request: AudioGenerationRequest) -> AudioGenerationResult:
        capability = request.capability.upper()
        if capability == "TTS":
            emotion = str(request.parameters.get("emotion") or "neutral")
            if emotion != "neutral" and emotion not in self.emotion_values:
                raise ValueError("AUDIO_PARAMETER_UNSUPPORTED: emotion")
            if set(request.parameters) - {"emotion", "speed", "response_format"}:
                raise ValueError("AUDIO_PARAMETER_UNSUPPORTED")
            path = "/audio/speech"
            payload = {"model": request.model_id, "voice": request.voice or "default", "input": request.prompt, "response_format": str(request.parameters.get("response_format") or "mp3")}
            if emotion in self.emotion_values: payload["emotion"] = emotion
            if "speed" in request.parameters:
                speed = float(request.parameters["speed"])
                if not 0.5 <= speed <= 2.0: raise ValueError("invalid audio speed")
                payload["speed"] = speed
        else:
            path = "/audio/generations"
            payload = {
                "model": request.model_id,
                "capability": capability,
                "prompt": request.prompt,
                "task_id": request.task_id,
                "source_audio_uri": request.source_audio_uri,
                "source_video_uri": request.source_video_uri,
                "duration_seconds": request.duration_seconds,
                **{key: value for key, value in request.parameters.items() if key not in {"model", "capability", "prompt", "task_id", "source_audio_uri", "source_video_uri"}},
            }
        response = self.transport.post(self.endpoint + path, headers=self._headers(), json=payload, timeout=300)
        response.raise_for_status()
        content_type = str(getattr(response, "headers", {}).get("content-type", "")).split(";", 1)[0]
        if content_type.startswith("audio/") or content_type == "application/octet-stream":
            content = bytes(response.content)
            if not content or len(content) > 25 * 1024 * 1024:
                raise ValueError("audio response is empty or exceeds limit")
            return AudioGenerationResult(request.provider_id, request.model_id, "data:" + (content_type if content_type.startswith("audio/") else "audio/mpeg") + ";base64," + base64.b64encode(content).decode("ascii"))
        data = response.json() if hasattr(response, "json") else {}
        uri = data.get("url") or data.get("audio_url") or data.get("audio_uri")
        remote = data.get("id") or data.get("task_id")
        if not uri and not remote:
            raise ValueError("audio provider response missing url or task id")
        status = str(data.get("status") or ("SUCCEEDED" if uri else "RUNNING")).upper()
        return AudioGenerationResult(request.provider_id, request.model_id, str(uri or ""), str(remote) if remote else None, status)


def provider_catalog() -> list[dict[str, Any]]:
    rows = []
    saved = load_audio_provider_config()
    provider_ids = list(dict.fromkeys([*AUDIO_PROVIDER_CATALOG, *saved]))
    for provider_id in provider_ids:
        config = {**AUDIO_PROVIDER_CATALOG.get(provider_id, {"priority": 150}), **saved.get(provider_id, {})}
        if not config.get("enabled", True):
            continue
        endpoint = os.getenv(f"AUDIO_{provider_id.upper().replace('-', '_')}_ENDPOINT", config["endpoint"])
        rows.append({"provider_id": provider_id, **config, "endpoint": endpoint})
    return sorted(rows, key=lambda item: (item["priority"], item["provider_id"]))


def resolve_provider(provider_id: str, capability: str, vault, transport) -> tuple[str, str, HttpAudioProvider]:
    requested = provider_id.strip().lower()
    candidates = provider_catalog()
    if requested and requested != "auto":
        candidates = [item for item in candidates if item["provider_id"] == requested]
    capability = capability.upper()
    for config in candidates:
        if capability not in config["capabilities"]:
            continue
        secret = vault.resolve(config["provider_id"]) if config["requires_credential"] else None
        if config["requires_credential"] and not secret:
            continue
        try:
            address = ipaddress.ip_address(urlsplit(config["endpoint"]).hostname or "")
            address=getattr(address,"ipv4_mapped",None) or address
            local = bool(config.get("local")) and (address.is_loopback or address.is_private) and not address.is_link_local and not address.is_unspecified and (not address.is_reserved or address.is_loopback)
        except ValueError:
            local = False
        adapter = HttpAudioProvider(transport, config["endpoint"], secret, local=local)
        if requested != "auto" or adapter.health_check():
            return config["provider_id"], config["default_model"], adapter
    raise ValueError(f"audio provider is not configured for {capability}")
