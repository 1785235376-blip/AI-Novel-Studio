import json
import os
import re
from pathlib import Path

from .storage import atomic_write

ALLOWED_CAPABILITIES = frozenset({"TTS", "TEXT_TO_AUDIO", "AUDIO_EDIT", "VIDEO_TO_AUDIO", "SFX", "FOLEY", "MUSIC"})


def config_path() -> Path:
    return Path(os.getenv("AUDIO_PROVIDER_CONFIG_PATH", str(Path.home() / ".ai-novel-studio" / "audio-providers.json")))


def load() -> dict:
    try:
        value = json.loads(config_path().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save(provider_id: str, *, endpoint: str, default_model: str, display_name: str, local: bool,
         enabled: bool, requires_credential: bool, capabilities: list[str]) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", provider_id):
        raise ValueError("invalid audio provider id")
    if not endpoint.startswith(("http://", "https://")):
        raise ValueError("invalid audio provider endpoint")
    normalized = list(dict.fromkeys(str(item).upper() for item in capabilities))
    if not normalized or any(item not in ALLOWED_CAPABILITIES for item in normalized):
        raise ValueError("invalid audio provider capabilities")
    data = load()
    data[provider_id] = {
        "endpoint": endpoint.rstrip("/"),
        "default_model": default_model.strip(),
        "display_name": (display_name or provider_id)[:120],
        "local": bool(local),
        "enabled": bool(enabled),
        "requires_credential": bool(requires_credential),
        "capabilities": normalized,
    }
    atomic_write(config_path(), json.dumps(data, ensure_ascii=False, indent=2))
    return data[provider_id]


def delete(provider_id: str) -> bool:
    data = load()
    if provider_id not in data:
        return False
    del data[provider_id]
    atomic_write(config_path(), json.dumps(data, ensure_ascii=False, indent=2))
    return True
